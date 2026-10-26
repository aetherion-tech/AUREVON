"""Persistent historical rebuilds use synthetic staged minute candles."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as DBSession

from app.broker.kite_auth import IST
from app.broker.kite_ticker import TickerWorker
from app.config import Settings
from app.db.models import (
    Base,
    HistoricalSpotBatch,
    HistoricalSpotCandle,
    Instrument,
    MarketCheckpoint,
    StoredBrick,
    StoredCandle,
)
from app.db.session import database_engine
from app.market.history_renko import rebuild_historical_renko
from app.market.persistence import MarketPersistence, PersistenceError
from app.market.tick_recording import TickRecorder
from app.market.warmup import HistoryRange, Session, SessionCalendar, WarmupPlan
from app.tools.replay_ticks import replay_events

START = datetime(2026, 10, 22, 9, 15, tzinfo=IST)
IDENTITY = "NFO:NIFTYTESTFUT:2026-10-29"


@pytest.fixture
def engine(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'renko.db').as_posix()}")
    Base.metadata.create_all(engine)
    with DBSession(engine) as db, db.begin():
        db.add(
            HistoricalSpotBatch(id="source", stream="test", token=111, provenance="{}")
        )
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
        db.flush()
        # Insert backwards to verify exchange-time order rather than insertion order.
        for index, price in reversed(list(enumerate([100, 130, 110, 140]))):
            stamp = START + timedelta(minutes=index)
            db.add(
                HistoricalSpotCandle(
                    stream="test",
                    token=111,
                    time=stamp.astimezone(UTC).isoformat(),
                    completed_at=(stamp + timedelta(minutes=1))
                    .astimezone(UTC)
                    .isoformat(),
                    payload=json.dumps(
                        {
                            "time": stamp.isoformat(),
                            "open": str(price),
                            "high": str(price),
                            "low": str(price),
                            "close": str(price),
                            "volume": "0",
                            "oi": None,
                        }
                    ),
                    batch_id="source",
                )
            )
    yield engine
    engine.dispose()


def plan():
    return WarmupPlan(
        "cold_start",
        START + timedelta(minutes=4),
        (HistoryRange("minute", START, START + timedelta(minutes=3)),),
        (),
        date(2026, 10, 21),
    )


def calendar():
    return SessionCalendar(
        date(2026, 10, 21),
        date(2026, 10, 23),
        (Session(START, START.replace(hour=15, minute=30)),),
    )


def rebuild(engine, *, settings=None, selected_plan=None, selected_calendar=None):
    return rebuild_historical_renko(
        engine,
        settings or Settings(_env_file=None, renko_box=10, renko_anchor=100),
        "test",
        111,
        222,
        IDENTITY,
        selected_plan or plan(),
        selected_calendar or calendar(),
    )


def snapshot(engine):
    with DBSession(engine) as db:
        return (
            [
                (r.token, r.time, r.payload)
                for r in db.scalars(select(StoredCandle).order_by(StoredCandle.time))
            ],
            [
                (r.index, r.payload)
                for r in db.scalars(select(StoredBrick).order_by(StoredBrick.index))
            ],
            [
                (r.revision, r.configuration, r.state)
                for r in db.scalars(select(MarketCheckpoint))
            ],
        )


def test_rebuild_orders_closes_emits_gaps_and_reversals_and_is_idempotent(engine):
    result = rebuild(engine)
    assert result.imported is True
    assert [(b.open, b.close) for b in result.bricks] == [
        (100, 110),
        (110, 120),
        (120, 130),
        (120, 110),
        (120, 130),
        (130, 140),
    ]
    assert [b.index for b in result.bricks] == list(range(6))
    assert result.bricks[0].ts == START + timedelta(minutes=2)
    assert result.bricks[-1].ts == START + timedelta(minutes=4)
    assert result.entries_enabled is False
    before = snapshot(engine)
    repeat = rebuild(engine)
    assert repeat.imported is False
    assert repeat.bricks == result.bricks
    assert snapshot(engine) == before
    state = json.loads(before[2][0][2])
    assert state["gap"] is True
    assert state["historical_import"]["entries_enabled"] is False
    assert state["counts"] == {"111": 4, "222": 0}


def test_existing_worker_restores_rebuilt_state_and_continues_without_duplicates(
    engine,
):
    initial = rebuild(engine)
    persistence = MarketPersistence(engine, "test", 111, 222, box=10, anchor=100)
    worker = TickerWorker(None, 111, 222, persistence=persistence)
    assert worker.gap_required is True
    assert persistence.renko.last == initial.renko.last
    assert persistence.renko.last_timestamp == START + timedelta(minutes=4)
    assert worker.candle_counts[111] == 4
    stamp = START + timedelta(minutes=4)
    worker._accept(
        {"instrument_token": 111, "exchange_timestamp": stamp, "last_price": 160}, stamp
    )
    worker.advance_candles(stamp + timedelta(minutes=1))
    assert persistence.renko.index == 8
    assert [b[0] for b in snapshot(engine)[1]] == list(range(8))
    with pytest.raises(PersistenceError, match="different state"):
        rebuild(engine)


def test_changed_source_or_configuration_never_overwrites_existing_stream(engine):
    rebuild(engine)
    before = snapshot(engine)
    with pytest.raises(PersistenceError, match="different state"):
        rebuild(
            engine, settings=Settings(_env_file=None, renko_box=20, renko_anchor=100)
        )
    assert snapshot(engine) == before
    with DBSession(engine) as db, db.begin():
        row = db.scalars(
            select(HistoricalSpotCandle).order_by(HistoricalSpotCandle.time)
        ).first()
        data = json.loads(row.payload)
        data.update(open="90", high="90", low="90", close="90")
        row.payload = json.dumps(data)
    with pytest.raises(PersistenceError, match="different state"):
        rebuild(engine)
    assert snapshot(engine) == before


def test_failed_brick_write_rolls_back_candles_and_checkpoint(engine):
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO renko_bricks"):
            raise OperationalError("insert", {}, Exception("private detail"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(PersistenceError, match="previous data retained") as error:
            rebuild(engine)
        assert "private detail" not in str(error.value)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert snapshot(engine) == ([], [], [])
    assert rebuild(engine).imported is True


@pytest.mark.parametrize(
    "settings",
    [
        Settings(_env_file=None, renko_mode="tick", renko_anchor=100),
        Settings(_env_file=None, renko_anchor=None),
    ],
)
def test_invalid_mode_or_anchor_has_no_writes(engine, settings):
    with pytest.raises(ValueError, match="minute_close"):
        rebuild(engine, settings=settings)
    assert snapshot(engine) == ([], [], [])


def test_checkpoint_restart_requires_merge_workflow(engine):
    with pytest.raises(ValueError, match="merge workflow"):
        rebuild(engine, selected_plan=replace(plan(), mode="checkpoint_restart"))
    assert snapshot(engine) == ([], [], [])


def test_empty_history_does_not_create_false_seed(engine):
    with DBSession(engine) as db, db.begin():
        for row in db.scalars(select(HistoricalSpotCandle)):
            db.delete(row)
    with pytest.raises(ValueError, match="No completed spot"):
        rebuild(engine)
    assert snapshot(engine) == ([], [], [])


def test_seed_only_history_persists_last_source_timestamp(engine):
    short = replace(plan(), spot=(HistoryRange("minute", START, START),))
    result = rebuild(engine, selected_plan=short)
    assert result.bricks == ()
    assert result.renko.last.index == -1
    assert result.renko.last_timestamp == START + timedelta(minutes=1)
    assert rebuild(engine, selected_plan=short).imported is False


def test_missing_sources_persist_quality_metadata_with_diagnostic_bricks(engine):
    with DBSession(engine) as db, db.begin():
        row = db.get(
            HistoricalSpotCandle,
            ("test", 111, (START + timedelta(minutes=1)).astimezone(UTC).isoformat()),
        )
        db.delete(row)
    result = rebuild(engine)
    assert result.spot_missing == 1
    state = json.loads(snapshot(engine)[2][0][2])
    assert state["gap"] is True
    assert state["historical_import"]["spot_missing"] == 1
    assert result.entries_enabled is False


def test_orphaned_outputs_are_preserved(engine):
    with DBSession(engine) as db, db.begin():
        db.add(StoredBrick(stream="test", index=0, payload="orphan"))
    before = snapshot(engine)
    with pytest.raises(PersistenceError, match="without a checkpoint"):
        rebuild(engine)
    assert snapshot(engine) == before


def test_wrong_catalog_identity_is_rejected(engine):
    with DBSession(engine) as db, db.begin():
        db.get(Instrument, ("NFO", "NIFTYTESTFUT")).instrument_token = 333
    with pytest.raises(ValueError, match="catalog identities"):
        rebuild(engine)
    assert snapshot(engine) == ([], [], [])


def test_cross_day_rebuild_keeps_grid_and_brick_indices(engine):
    tomorrow = START + timedelta(days=1)
    with DBSession(engine) as db, db.begin():
        db.add(
            HistoricalSpotCandle(
                stream="test",
                token=111,
                time=tomorrow.astimezone(UTC).isoformat(),
                completed_at=(tomorrow + timedelta(minutes=1))
                .astimezone(UTC)
                .isoformat(),
                payload=json.dumps(
                    {
                        "time": tomorrow.isoformat(),
                        "open": "160",
                        "high": "160",
                        "low": "160",
                        "close": "160",
                        "volume": "0",
                        "oi": None,
                    }
                ),
                batch_id="source",
            )
        )
    selected_plan = replace(
        plan(),
        cutoff=tomorrow + timedelta(minutes=1),
        spot=(*plan().spot, HistoryRange("minute", tomorrow, tomorrow)),
    )
    selected_calendar = SessionCalendar(
        date(2026, 10, 21),
        date(2026, 10, 23),
        (
            *calendar().sessions,
            Session(tomorrow, tomorrow.replace(hour=15, minute=30)),
        ),
    )
    result = rebuild(
        engine, selected_plan=selected_plan, selected_calendar=selected_calendar
    )
    assert len(result.bricks) == 8
    assert result.bricks[-1].index == 7
    assert result.bricks[-1].close == 160
    assert result.bricks[-1].ts == tomorrow + timedelta(minutes=1)


def test_idempotent_import_issues_no_insert_update_or_delete(engine):
    rebuild(engine)
    writes = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.split()[0] in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert rebuild(engine).imported is False
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert writes == []


@pytest.mark.asyncio
async def test_buffered_history_merge_filters_overlap_and_keeps_unfinished_bars(engine):
    rebuild(engine)
    store = MarketPersistence(engine, "test", 111, 222, box=10, anchor=100)
    worker = TickerWorker(Mock(), 111, 222)
    boundary = START + timedelta(minutes=4)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        for token, stamp, price, volume in (
            (111, boundary - timedelta(seconds=1), 999, 0),
            (222, START - timedelta(seconds=1), 999, 10),
            (111, boundary, 150, 0),
            (222, START + timedelta(minutes=4), 150, 1000),
            (111, boundary, 160, 0),
            (222, START + timedelta(minutes=4, seconds=59), 160, 1010),
        ):
            worker._enqueue(
                [
                    {
                        "instrument_token": token,
                        "exchange_timestamp": stamp,
                        "last_price": price,
                        "volume_traded": volume,
                        "oi": 20,
                    }
                ],
                boundary,
            )
        await asyncio.sleep(0)
        assert worker.accepted == 0
        assert worker.queue.qsize() == 6
        with pytest.raises(ValueError, match="Cannot advance"):
            worker.advance_candles(boundary)
        worker.merge_history(store, {111: boundary, 222: START})
        await worker.queue.join()
        assert worker.history_overlap == 2
        assert worker.accepted == 4
        assert worker.candle_counts == {111: 4, 222: 0}
        assert worker.candles[222].current.volume == 10
        assert worker.candles[222].current.partial is True
        worker.advance_candles(START + timedelta(minutes=4, seconds=59))
        assert worker.candle_counts == {111: 4, 222: 0}
        worker.advance_candles(START + timedelta(minutes=5))
        assert worker.candle_counts == {111: 5, 222: 1}
        assert store.renko.index == 8
        assert worker.status()["entries_enabled"] is False
        assert worker.gap_required is True
        await worker.stop()
    restored = TickerWorker(
        None,
        111,
        222,
        persistence=MarketPersistence(
            engine,
            "test",
            111,
            222,
            box=10,
            anchor=100,
        ),
    )
    assert restored.candle_counts == {111: 5, 222: 1}
    assert [b[0] for b in snapshot(engine)[1]] == list(range(8))


@pytest.mark.asyncio
async def test_merge_invalid_boundaries_leave_queue_blocked(engine):
    rebuild(engine)
    worker = TickerWorker(Mock(), 111, 222)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        boundary = START + timedelta(minutes=4)
        for boundaries in (
            {111: boundary},
            {111: boundary.replace(tzinfo=None), 222: START},
            {111: boundary - timedelta(minutes=1), 222: START},
            {111: boundary, 222: START + timedelta(minutes=1)},
        ):
            store = MarketPersistence(engine, "test", 111, 222, box=10, anchor=100)
            with pytest.raises(ValueError):
                worker.merge_history(store, boundaries)
            assert worker.persistence is None
            assert worker.status()["history_pending"] is True
        await worker.stop()  # A blocked consumer must not hang on queue.join().


@pytest.mark.asyncio
async def test_buffer_overflow_remains_gapped_after_history_merge(engine):
    rebuild(engine)
    worker = TickerWorker(Mock(), 111, 222, capacity=1)
    boundary = START + timedelta(minutes=4)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        tick = {
            "instrument_token": 111,
            "exchange_timestamp": boundary,
            "last_price": 150,
        }
        worker._enqueue([tick, tick], boundary)
        assert worker.dropped == 1
        worker.merge_history(
            MarketPersistence(engine, "test", 111, 222, box=10, anchor=100),
            {111: boundary, 222: START},
        )
        await worker.queue.join()
        assert worker.gap_required is True
        assert worker.candles[111].current.partial is True
        await worker.stop()


@pytest.mark.asyncio
async def test_handoff_recording_replays_and_missing_tail_is_not_fabricated(
    engine, tmp_path
):
    rebuild(engine)
    boundary = START + timedelta(minutes=5)
    recorder = TickRecorder(tmp_path, 111, 222)
    worker = TickerWorker(Mock(), 111, 222, recorder=recorder, clock=lambda: boundary)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        # The missing 09:19 minute belongs to recovery, never to a queued fragment.
        for stamp in (boundary - timedelta(seconds=1), boundary):
            worker._enqueue(
                [
                    {
                        "instrument_token": 111,
                        "exchange_timestamp": stamp,
                        "last_price": 160,
                    }
                ],
                boundary,
            )
        worker.merge_history(
            MarketPersistence(engine, "test", 111, 222, box=10, anchor=100),
            {111: boundary, 222: boundary},
        )
        await worker.queue.join()
        worker.advance_candles(boundary + timedelta(minutes=1))
        assert worker.candle_counts == {111: 5, 222: 0}
        assert worker.closed_candles[111][-1].time == boundary
        await worker.stop()
    events = list(replay_events(sorted(recorder.directory.glob("*.jsonl"))))
    assert len(events) == 1
    assert events[0]["candle"]["time"] == boundary
    assert events[0]["candle"]["partial"] is True


@pytest.mark.asyncio
async def test_failed_handoff_save_keeps_live_worker_and_queue_untouched(engine):
    rebuild(engine)
    before = snapshot(engine)
    worker = TickerWorker(Mock(), 111, 222)
    boundary = START + timedelta(minutes=4)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        worker._enqueue(
            [
                {
                    "instrument_token": 111,
                    "exchange_timestamp": boundary,
                    "last_price": 160,
                }
            ],
            boundary,
        )
        store = MarketPersistence(engine, "test", 111, 222, box=10, anchor=100)
        with patch.object(store, "save", side_effect=PersistenceError("failed")):
            with pytest.raises(PersistenceError, match="failed"):
                worker.merge_history(store, {111: boundary, 222: START})
        assert worker.persistence is None
        assert worker.status()["history_pending"] is True
        assert worker.queue.qsize() == 1
        assert snapshot(engine) == before
        await worker.stop()
