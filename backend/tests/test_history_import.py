"""Direct historical volume, session VWAP and conservative live handoff."""

import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.broker.kite_auth import IST
from app.db.models import (
    Base,
    HistoricalContextBatch,
    HistoricalContextCandle,
    HistoricalSpotBatch,
    HistoricalSpotCandle,
    MarketCheckpoint,
    StoredBrick,
    StoredCandle,
)
from app.db.session import database_engine
from app.market.candles_5m import CandleBuilder, MarketCandle
from app.market.history_import import build_historical_seed
from app.market.persistence import builder_state, encode, restore_builder
from app.market.warmup import HistoryRange, Session, SessionCalendar, WarmupPlan

START = datetime(2026, 10, 22, 9, 15, tzinfo=IST)
IDENTITY = "NFO:NIFTYTESTFUT:2026-10-29"


def candle(index=0, volume=100, day=0):
    start = START + timedelta(minutes=index * 5, days=day)
    return MarketCandle(
        start,
        start + timedelta(minutes=5),
        Decimal(100),
        Decimal(110),
        Decimal(90),
        Decimal(100),
        Decimal(volume),
        None,
        False,
    )


def import_bar(builder, bar, cutoff=None):
    opening = bar.time.replace(hour=9, minute=15)
    return builder.import_completed(
        bar,
        session_open=opening,
        session_close=opening.replace(hour=15, minute=30),
        cutoff=cutoff or bar.end,
    )


def test_direct_volume_weights_hlc3_instead_of_counter_deltas():
    builder = CandleBuilder()
    first = import_bar(builder, candle())
    second = import_bar(
        builder,
        replace(
            candle(1, 300), high=Decimal(140), low=Decimal(100), close=Decimal(120)
        ),
    )
    assert first.volume == 100
    assert second.volume == 300
    assert builder.total_volume == 400
    assert second.vwap == Decimal(115)
    assert second.vwap_partial is False
    assert builder.cumulative is None


def test_gap_and_late_start_preserve_partial_vwap_until_day_reset():
    builder = CandleBuilder()
    assert import_bar(builder, candle(1)).vwap_partial is True
    assert import_bar(builder, candle(3)).vwap_partial is True
    tomorrow = import_bar(builder, candle(0, 200, day=1))
    assert tomorrow.vwap_partial is False
    assert builder.total_volume == 200


def test_zero_volume_and_missing_oi_are_not_invented():
    builder = CandleBuilder()
    first = import_bar(builder, candle(volume=0))
    assert first.vwap is None and first.oi is None
    assert first.vwap_partial is False
    second = import_bar(builder, candle(1, 200))
    assert second.vwap == 100
    assert builder.total_volume == 200


def test_first_live_tick_does_not_subtract_history_from_exchange_counter():
    builder = CandleBuilder()
    import_bar(builder, candle())
    builder.on_tick(120, START + timedelta(minutes=5), cumulative_volume=5000)
    assert builder.current.volume == 0
    assert builder.current.partial and builder.vwap_partial
    builder.on_tick(
        130, START + timedelta(minutes=5, seconds=1), cumulative_volume=5020
    )
    assert builder.current.volume == 20
    assert builder.total_volume == 100


def test_spot_import_has_no_volume_oi_or_vwap():
    builder = CandleBuilder(1, futures=False)
    bar = replace(candle(), end=START + timedelta(minutes=1), oi=Decimal(50))
    imported = import_bar(builder, bar)
    assert imported.volume is None and imported.oi is None and imported.vwap is None


def test_duplicate_and_active_builder_import_reject_without_mutation():
    builder = CandleBuilder()
    import_bar(builder, candle())
    before = encode(builder_state(builder))
    with pytest.raises(ValueError):
        import_bar(builder, candle())
    assert encode(builder_state(builder)) == before
    builder.on_tick(100, candle(1).time, cumulative_volume=1000)
    before = encode(builder_state(builder))
    with pytest.raises(ValueError):
        import_bar(builder, candle(1))
    assert encode(builder_state(builder)) == before


@pytest.mark.parametrize(
    "change",
    [
        {"volume": Decimal(-1)},
        {"volume": None},
        {"high": Decimal("NaN")},
        {"low": Decimal(101)},
        {"oi": Decimal(-1)},
        {"time": START.replace(tzinfo=None)},
    ],
)
def test_invalid_history_does_not_mutate(change):
    builder = CandleBuilder()
    before = encode(builder_state(builder))
    with pytest.raises(ValueError):
        import_bar(builder, replace(candle(), **change))
    assert encode(builder_state(builder)) == before


def test_unfinished_bar_rejected_and_seed_checkpoint_roundtrips():
    builder = CandleBuilder()
    with pytest.raises(ValueError):
        import_bar(builder, candle(), cutoff=START + timedelta(minutes=4))
    import_bar(builder, candle())
    restored = CandleBuilder()
    restore_builder(restored, json.loads(encode(builder_state(builder))))
    assert builder_state(builder) == builder_state(restored)
    assert import_bar(restored, candle(1, 300)).vwap == 100


@pytest.fixture
def engine(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'seed.db').as_posix()}")
    Base.metadata.create_all(engine)
    with DBSession(engine) as db, db.begin():
        db.add(HistoricalContextBatch(id="context", stream="test", provenance="{}"))
        db.add(
            HistoricalSpotBatch(id="spot", stream="test", token=111, provenance="{}")
        )
        db.flush()
        for index in (0, 1):
            bar = candle(index, 100 + 200 * index)
            payload = asdict(bar)
            payload = {
                k: payload[k]
                for k in ("time", "open", "high", "low", "close", "volume", "oi")
            }
            db.add(
                HistoricalContextCandle(
                    stream="test",
                    identity=IDENTITY,
                    kind="futures_5minute",
                    time=bar.time.astimezone(UTC).isoformat(),
                    completed_at=bar.end.astimezone(UTC).isoformat(),
                    payload=encode(payload),
                    batch_id="context",
                )
            )
        for index in range(10):
            stamp = START + timedelta(minutes=index)
            db.add(
                HistoricalSpotCandle(
                    stream="test",
                    token=111,
                    time=stamp.astimezone(UTC).isoformat(),
                    completed_at=(stamp + timedelta(minutes=1))
                    .astimezone(UTC)
                    .isoformat(),
                    payload=encode(
                        {
                            "time": stamp,
                            "open": "100",
                            "high": "100",
                            "low": "100",
                            "close": "100",
                            "volume": "0",
                            "oi": None,
                        }
                    ),
                    batch_id="spot",
                )
            )
    yield engine
    engine.dispose()


def seed(engine, selected_plan=None):
    plan = selected_plan or WarmupPlan(
        "cold_start",
        START + timedelta(minutes=10),
        (HistoryRange("minute", START, START + timedelta(minutes=9)),),
        (HistoryRange("5minute", START, START + timedelta(minutes=5)),),
        date(2026, 10, 21),
    )
    calendar = SessionCalendar(
        date(2026, 10, 21),
        date(2026, 10, 23),
        (Session(START, START.replace(hour=15, minute=30)),),
    )
    return build_historical_seed(engine, "test", 111, IDENTITY, plan, calendar)


def test_staged_seed_is_repeatable_and_does_not_change_live_tables(engine):
    first, second = seed(engine), seed(engine)
    assert first.spot_missing == first.futures_missing == 0
    assert [bar.volume for bar in first.futures_candles] == [100, 300]
    assert first.futures.total_volume == 400
    assert first.futures.vwap_partial is False
    assert first.entries_enabled is False
    assert all(bar.volume is None for bar in first.spot_candles)
    assert builder_state(first.futures) == builder_state(second.futures)
    assert first.futures_candles == second.futures_candles
    with DBSession(engine) as db:
        for model in (StoredCandle, StoredBrick, MarketCheckpoint):
            assert db.scalars(select(model)).all() == []


def test_missing_tail_is_reported_without_inventing_candles(engine):
    plan = WarmupPlan(
        "cold_start",
        START + timedelta(minutes=15),
        (),
        (HistoryRange("5minute", START, START + timedelta(minutes=10)),),
        date(2026, 10, 21),
    )
    result = seed(engine, plan)
    assert result.futures_missing == 1
    assert len(result.futures_candles) == 2
    assert result.futures.vwap_partial is True


def test_corrupt_source_boundaries_fail_without_writing(engine):
    with DBSession(engine) as db, db.begin():
        row = db.scalars(select(HistoricalContextCandle)).first()
        row.completed_at = START.astimezone(UTC).isoformat()
    with pytest.raises(ValueError, match="boundaries"):
        seed(engine)


def test_older_session_gap_does_not_taint_complete_current_vwap(engine):
    previous = START - timedelta(days=1)
    selected_plan = WarmupPlan(
        "cold_start",
        START + timedelta(minutes=10),
        (),
        (
            HistoryRange("5minute", previous, previous),
            HistoryRange("5minute", START, START + timedelta(minutes=5)),
        ),
        date(2026, 10, 21),
    )
    calendar = SessionCalendar(
        date(2026, 10, 21),
        date(2026, 10, 23),
        (
            Session(previous, previous.replace(hour=15, minute=30)),
            Session(START, START.replace(hour=15, minute=30)),
        ),
    )
    result = build_historical_seed(
        engine, "test", 111, IDENTITY, selected_plan, calendar
    )
    assert result.futures_missing == 1
    assert result.futures.vwap_partial is False
    assert result.futures.total_volume == 400
    assert result.entries_enabled is False
