"""Offline recovery uses synthetic broker responses and isolated SQLite streams."""

import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as DBSession

from app.broker.kite_auth import IST, AuthError, KiteAuth
from app.broker.kite_ticker import TickerWorker
from app.config import Settings
from app.db.models import (
    Base,
    HistoricalContextBatch,
    HistoricalContextCandle,
    HistoricalSpotBatch,
    HistoricalSpotCandle,
    Instrument,
    MarketCheckpoint,
    StoredBrick,
    StoredCandle,
)
from app.db.session import database_engine
from app.market.candles_5m import MarketCandle
from app.market.persistence import (
    MarketPersistence,
    PersistenceError,
    brick_from,
    encode,
)
from app.market.recovery import recover_missing_history
from app.market.recovery_requests import RecoveryRequestError
from app.market.renko_builder import RenkoBuilder
from app.market.warmup import Session, SessionCalendar

START = datetime(2026, 10, 23, 9, 15, tzinfo=IST)
END = START + timedelta(minutes=15)
IDENTITY = "NFO:NIFTYTESTFUT:2026-10-29"
SETTINGS = Settings(_env_file=None, renko_box=10, renko_anchor=100)
CALENDAR = SessionCalendar(
    date(2026, 10, 23),
    date(2026, 10, 26),
    (
        Session(START, START.replace(hour=15, minute=30)),
        Session(START.replace(day=26), START.replace(day=26, hour=15, minute=30)),
    ),
)
PRICES = [100, 130, 110, 140, 120, 150, 140, 160, 130, 140, 160, 150, 170, 150, 180]


def candle(token, index, *, partial=False, oi=20):
    stamp = START + timedelta(minutes=index)
    price = Decimal(PRICES[index])
    return MarketCandle(
        stamp,
        stamp + timedelta(minutes=1 if token == 111 else 5),
        price,
        price,
        price,
        price,
        Decimal((index + 1) * 10) if token == 222 else None,
        Decimal(oi) if token == 222 and oi is not None else None,
        partial,
    )


def store(engine):
    return MarketPersistence(engine, "test", 111, 222, box=10, anchor=100)


@pytest.fixture
def engine(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'recovery.db').as_posix()}")
    Base.metadata.create_all(engine)
    with DBSession(engine) as db, db.begin():
        for exchange, symbol, token, expiry, kind in (
            ("NSE", "NIFTY 50", 111, None, "EQ"),
            ("NFO", "NIFTYTESTFUT", 222, date(2026, 10, 29), "FUT"),
        ):
            db.add(
                Instrument(
                    exchange=exchange,
                    tradingsymbol=symbol,
                    instrument_token=token,
                    name="NIFTY",
                    expiry=expiry,
                    strike=0,
                    tick_size=0.05,
                    lot_size=65,
                    instrument_type=kind,
                    segment=exchange,
                )
            )
    persistence = store(engine)
    worker = TickerWorker(None, 111, 222, persistence=persistence, clock=lambda: END)
    for token, indices in ((111, [i for i in range(15) if i != 1]), (222, [0, 10])):
        for i in indices:
            result = worker.candles[token].import_completed(
                candle(token, i),
                session_open=START,
                session_close=START.replace(hour=15, minute=30),
                cutoff=END,
            )
            worker._store_candles(token, [result])
    worker._track_gap("disconnect", END, persist=False)
    worker.gaps.mark(111, "overflow", START + timedelta(minutes=1), resume_after=END)
    worker.gaps.mark(222, "overflow", START + timedelta(minutes=5), resume_after=END)
    persistence.save(worker)
    yield engine
    engine.dispose()


def broker(*, missing=(), oi=20, fail=False):
    auth = Mock(spec=KiteAuth)

    def historical(token, interval, start, end, **kwargs):
        if fail:
            raise ValueError("Synthetic broker failure")
        rows = []
        step = timedelta(minutes=1 if interval == "minute" else 5)
        at = start
        while at <= end:
            index = int((at - START).total_seconds() // 60)
            if (token, index) not in missing:
                bar = candle(token, index % len(PRICES), oi=oi)
                row = [
                    at.isoformat(),
                    str(bar.open),
                    str(bar.high),
                    str(bar.low),
                    str(bar.close),
                    str(bar.volume or 0),
                ]
                if token == 222:
                    row.append(str(bar.oi) if bar.oi is not None else None)
                rows.append(row)
            at += step
        return {"candles": rows}

    auth.historical_data.side_effect = historical
    return auth


def recover(
    engine,
    auth=None,
    *,
    cutoff=END,
    settings=SETTINGS,
    identity=IDENTITY,
    calendar=CALENDAR,
    correct_partial=False,
):
    return recover_missing_history(
        auth or broker(),
        engine,
        settings,
        "test",
        111,
        222,
        identity,
        calendar,
        cutoff,
        correct_partial=correct_partial,
    )


def snapshot(engine):
    with DBSession(engine) as db:
        return {
            model.__tablename__: [
                dict(r.__dict__) | {"_sa_instance_state": None}
                for r in db.scalars(select(model))
            ]
            for model in (
                StoredCandle,
                StoredBrick,
                MarketCheckpoint,
                HistoricalSpotBatch,
                HistoricalSpotCandle,
                HistoricalContextBatch,
                HistoricalContextCandle,
            )
        }


def state(engine):
    with DBSession(engine) as db:
        return json.loads(db.get(MarketCheckpoint, "test").state)


def test_recovers_only_missing_bars_and_matches_uninterrupted_renko_vwap(engine):
    auth = broker()
    result = recover(engine, auth)
    assert result.imported is True
    assert (result.spot_inserted, result.futures_inserted) == (1, 1)
    assert (result.spot_missing, result.futures_missing) == (0, 0)
    assert result.entries_enabled is False
    requests = auth.historical_data.call_args_list
    assert [(c.args[0], c.args[1], c.args[2]) for c in requests] == [
        (111, "minute", START + timedelta(minutes=1)),
        (222, "5minute", START + timedelta(minutes=5)),
    ]
    assert requests[1].kwargs["oi"] is True
    reference = RenkoBuilder(10, 100)
    expected = [
        b
        for i in range(15)
        for b in reference.on_price(candle(111, i).close, candle(111, i).end)
    ]
    with DBSession(engine) as db:
        actual = [
            json.loads(r.payload)
            for r in db.scalars(select(StoredBrick).order_by(StoredBrick.index))
        ]
        assert [brick_from(b) for b in actual] == expected
        futures = [
            json.loads(r.payload)
            for r in db.scalars(
                select(StoredCandle)
                .where(StoredCandle.token == 222)
                .order_by(StoredCandle.time)
            )
        ]
    expected_vwap = (
        sum(candle(222, i).close * candle(222, i).volume for i in (0, 5, 10)) / 180
    )
    assert Decimal(futures[-1]["vwap"]) == expected_vwap
    assert futures[-1]["vwap_partial"] is False
    saved = state(engine)
    assert saved["gap"] is True
    assert saved["gaps"]
    assert saved["counts"] == {"111": 15, "222": 3}
    assert saved["recovery"]["entries_enabled"] is False


def test_identical_recovery_has_no_requests_or_writes(engine):
    recover(engine)
    before = snapshot(engine)
    auth, writes = broker(), []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.split()[0] in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        repeat = recover(engine, auth)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert repeat.imported is False
    assert auth.historical_data.call_count == 0
    assert writes == []
    assert snapshot(engine) == before


def test_missing_sources_are_not_fabricated_and_quality_survives_restart(engine):
    result = recover(engine, broker(missing={(111, 1), (222, 5)}, oi=None))
    assert (result.spot_missing, result.futures_missing) == (1, 1)
    worker = TickerWorker(None, 111, 222, persistence=store(engine), clock=lambda: END)
    assert worker.gap_required is True
    assert worker.status()["entries_enabled"] is False
    assert worker.candles[111]._closed_until == END
    assert worker.candles[222].vwap_partial is True
    worker.persistence.save(worker)
    assert state(engine)["recovery"]["spot_missing"] == 1


def test_missing_oi_and_existing_partial_bars_stay_explicit(engine):
    with DBSession(engine) as db, db.begin():
        row = db.scalars(select(StoredCandle).where(StoredCandle.token == 111)).first()
        payload = json.loads(row.payload)
        payload["partial"] = True
        row.payload = encode(payload)
    result = recover(engine, broker(oi=None))
    assert result.retained_partial == 1
    assert result.oi_missing == 1
    assert result.entries_enabled is False


def test_failed_download_leaves_every_table_untouched(engine):
    before = snapshot(engine)
    with pytest.raises(ValueError, match="broker failure"):
        recover(engine, broker(fail=True))
    assert snapshot(engine) == before


def test_failed_derived_write_rolls_back_sources_and_all_outputs(engine):
    before = snapshot(engine)

    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO renko_bricks"):
            raise OperationalError("insert", {}, Exception("private detail"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(PersistenceError, match="previous data retained") as error:
            recover(engine)
        assert "private detail" not in str(error.value)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert snapshot(engine) == before
    assert recover(engine).imported is True


def test_concurrent_writer_is_detected_after_network_fetch(engine):
    before = snapshot(engine)
    auth = broker()
    original = auth.historical_data.side_effect

    def race(*args, **kwargs):
        rows = original(*args, **kwargs)
        with DBSession(engine) as db, db.begin():
            db.execute(update(MarketCheckpoint).values(revision=99))
        return rows

    auth.historical_data.side_effect = race
    with pytest.raises(PersistenceError, match="changed during recovery"):
        recover(engine, auth)
    after = snapshot(engine)
    assert after["market_candles"] == before["market_candles"]
    assert after["renko_bricks"] == before["renko_bricks"]
    assert after["historical_spot_candles"] == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"identity": "NFO:OTHER:2026-10-29"},
        {"settings": Settings(_env_file=None, renko_mode="tick", renko_anchor=100)},
        {"settings": Settings(_env_file=None, renko_anchor=None)},
        {"settings": Settings(_env_file=None, renko_box=20, renko_anchor=100)},
        {"cutoff": END - timedelta(minutes=1)},
        {"calendar": SessionCalendar(date(2026, 10, 26), date(2026, 10, 26), ())},
    ],
)
def test_invalid_recovery_scope_has_no_writes(engine, kwargs):
    before = snapshot(engine)
    with pytest.raises((ValueError, PersistenceError)):
        recover(engine, **kwargs)
    assert snapshot(engine) == before


def test_preserves_unfinished_live_fragment_but_recovers_elapsed_one(engine):
    # Add one unfinished spot bucket and one elapsed, never-completed futures fragment.
    with DBSession(engine) as db, db.begin():
        row = db.get(MarketCheckpoint, "test")
        data = json.loads(row.state)
        data["builders"]["111"]["current"] = asdict(
            replace(
                candle(111, 14),
                time=END + timedelta(minutes=5),
                end=END + timedelta(minutes=6),
            )
        )
        data["builders"]["111"]["last_time"] = END + timedelta(minutes=5)
        data["builders"]["222"]["current"] = asdict(
            replace(candle(222, 5), time=END, end=END + timedelta(minutes=5))
        )
        row.state = encode(data)
    recover(engine, cutoff=END + timedelta(minutes=5, seconds=30))
    saved = state(engine)
    assert saved["builders"]["111"]["current"]["time"] == str(
        END + timedelta(minutes=5)
    )
    assert saved["builders"]["111"]["current"]["partial"] is True
    assert saved["builders"]["222"]["current"] is None
    assert "222" in saved["recovery"]["elapsed_fragments"]


def test_later_retry_fills_previously_unavailable_sources(engine):
    first = recover(engine, broker(missing={(111, 1), (222, 5)}))
    assert first.spot_missing == first.futures_missing == 1
    second = recover(engine)
    assert second.spot_missing == second.futures_missing == 0
    assert second.spot_inserted == second.futures_inserted == 1
    assert recover(engine).imported is False


def test_staged_source_conflict_is_not_silently_corrected(engine):
    source = candle(111, 1)
    payload = {
        "time": source.time,
        "open": "999",
        "high": "999",
        "low": "999",
        "close": "999",
        "volume": "0",
        "oi": None,
    }
    with DBSession(engine) as db, db.begin():
        db.add(
            HistoricalSpotBatch(id="prior", stream="test", token=111, provenance="{}")
        )
        db.flush()

        db.add(
            HistoricalSpotCandle(
                stream="test",
                token=111,
                time=source.time.astimezone(UTC).isoformat(),
                completed_at=source.end.astimezone(UTC).isoformat(),
                payload=encode(payload),
                batch_id="prior",
            )
        )
    before = snapshot(engine)
    with pytest.raises(ValueError, match="explicit correction"):
        recover(engine)
    assert snapshot(engine) == before


def test_weekend_recovery_uses_sessions_and_resets_vwap(engine):
    monday = START.replace(day=26)
    selected = SessionCalendar(
        date(2026, 10, 23),
        date(2026, 10, 26),
        (
            Session(START, END),
            Session(monday, monday + timedelta(minutes=15)),
        ),
    )
    auth = broker()
    result = recover(
        engine, auth, cutoff=monday + timedelta(minutes=10), calendar=selected
    )
    assert result.spot_inserted == 11
    assert result.futures_inserted == 3
    assert all(c.args[2].weekday() < 5 for c in auth.historical_data.call_args_list)
    with DBSession(engine) as db:
        rows = db.scalars(
            select(StoredCandle)
            .where(StoredCandle.token == 222)
            .order_by(StoredCandle.time)
        ).all()
        final = json.loads(rows[-1].payload)
        assert final["vwap_partial"] is False
    assert state(engine)["next_index"] > 0


def test_excessive_downtime_fails_before_broker_requests(engine):
    before = snapshot(engine)
    auth = broker()
    with pytest.raises(ValueError, match="automatic recovery limit"):
        recover(
            engine,
            auth,
            cutoff=START.replace(day=26),
            settings=Settings(
                _env_file=None, renko_box=10, renko_anchor=100, recovery_max_gap_days=1
            ),
        )
    assert auth.historical_data.call_count == 0
    assert snapshot(engine) == before


def test_new_worker_continues_rebuilt_indices_and_preserves_recovery_evidence(engine):
    recover(engine)
    worker = TickerWorker(None, 111, 222, persistence=store(engine), clock=lambda: END)
    previous_index = worker.persistence.renko.index
    worker._accept(
        {"instrument_token": 111, "exchange_timestamp": END, "last_price": 200}, END
    )
    worker.advance_candles(END + timedelta(minutes=1))
    assert worker.persistence.renko.index == previous_index + 2
    with DBSession(engine) as db:
        indices = list(
            db.scalars(select(StoredBrick.index).order_by(StoredBrick.index))
        )
    assert indices == list(range(previous_index + 2))
    assert state(engine)["recovery"]["futures_identity"] == IDENTITY
    assert worker.status()["entries_enabled"] is False


def corrupt_partial(engine, token, index):
    """Create a completed sampled bar and its matching staged sampled source."""
    source = replace(
        candle(token, index),
        open=Decimal(300),
        high=Decimal(300),
        low=Decimal(300),
        close=Decimal(300),
        partial=True,
    )
    stamp = source.time.astimezone(UTC).isoformat()
    batch_id = f"sampled-{token}"
    with DBSession(engine) as db, db.begin():
        db.get(StoredCandle, ("test", token, stamp)).payload = encode(asdict(source))
        payload = {
            k: v
            for k, v in asdict(source).items()
            if k in ("time", "open", "high", "low", "close", "volume", "oi")
        }
        if token == 111:
            payload["volume"] = "0"
            db.add(
                HistoricalSpotBatch(
                    id=batch_id, stream="test", token=token, provenance="{}"
                )
            )
            db.flush()
            db.add(
                HistoricalSpotCandle(
                    stream="test",
                    token=token,
                    time=stamp,
                    completed_at=source.end.astimezone(UTC).isoformat(),
                    payload=encode(payload),
                    batch_id=batch_id,
                )
            )
        else:
            db.add(HistoricalContextBatch(id=batch_id, stream="test", provenance="{}"))
            db.flush()
            db.add(
                HistoricalContextCandle(
                    stream="test",
                    identity=IDENTITY,
                    kind="futures_5minute",
                    time=stamp,
                    completed_at=source.end.astimezone(UTC).isoformat(),
                    payload=encode(payload),
                    batch_id=batch_id,
                )
            )


def test_explicit_partial_correction_rebuilds_bricks_vwap_and_archives_old_sources(
    engine,
):
    recover(engine)
    baseline_bricks = snapshot(engine)["renko_bricks"]
    corrupt_partial(engine, 111, 2)
    corrupt_partial(engine, 222, 0)
    # Default mode retains partial sources and derives their diagnostic outputs.
    assert recover(engine).retained_partial == 2
    assert snapshot(engine)["renko_bricks"] != baseline_bricks
    result = recover(engine, correct_partial=True)
    assert result.spot_corrected == result.futures_corrected == 1
    assert result.spot_inserted == result.futures_inserted == 0
    assert result.retained_partial == 0
    assert snapshot(engine)["renko_bricks"] == baseline_bricks
    with DBSession(engine) as db:
        audits = [
            json.loads(r.provenance)
            for model in (HistoricalSpotBatch, HistoricalContextBatch)
            for r in db.scalars(select(model))
        ]
        repaired = [a for a in audits if a.get("market_corrections")]
        assert len(repaired) == 2
        assert all(a["market_corrections"][0]["before"]["partial"] for a in repaired)
        assert all(
            a["staged_replacements"][0]["before_batch_id"].startswith("sampled-")
            for a in repaired
        )
    before = snapshot(engine)
    auth = broker()
    assert recover(engine, auth, correct_partial=True).imported is False
    assert auth.historical_data.call_count == 0
    assert snapshot(engine) == before


def test_partial_correction_missing_source_is_retained_and_reported(engine):
    recover(engine)
    corrupt_partial(engine, 111, 2)
    result = recover(engine, broker(missing={(111, 2)}), correct_partial=True)
    assert result.retained_partial == 1
    assert result.spot_corrected == 0
    assert state(engine)["gap"] is True


def test_correction_rolls_back_original_sources_and_outputs_together(engine):
    recover(engine)
    corrupt_partial(engine, 222, 0)
    before = snapshot(engine)

    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO renko_bricks"):
            raise OperationalError("insert", {}, Exception("private"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(PersistenceError, match="previous data retained"):
            recover(engine, correct_partial=True)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert snapshot(engine) == before


def test_transient_recovery_request_retries_without_restarting_successful_downloads(
    engine,
):
    auth, sleeps = broker(), []
    original = auth.historical_data.side_effect
    count = 0

    def flaky(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise AuthError("temporary", 429, retryable=True)
        return original(*args, **kwargs)

    auth.historical_data.side_effect = flaky
    with patch("app.market.recovery_requests.sleep", side_effect=sleeps.append):
        result = recover(engine, auth)
    assert result.request_retries == 1
    assert sleeps == [1]
    assert [c.args[0] for c in auth.historical_data.call_args_list] == [111, 222, 222]


def test_retry_exhaustion_does_not_commit_earlier_successful_source_fetch(engine):
    before = snapshot(engine)
    auth, sleeps = broker(), []
    original = auth.historical_data.side_effect

    def fail_future(*args, **kwargs):
        if args[0] == 222:
            raise AuthError("temporary", 429, retryable=True)
        return original(*args, **kwargs)

    auth.historical_data.side_effect = fail_future
    with patch("app.market.recovery_requests.sleep", side_effect=sleeps.append):
        with pytest.raises(RecoveryRequestError, match="exhausted"):
            recover(engine, auth)
    assert sleeps == [1, 2, 4, 8]
    assert snapshot(engine) == before
