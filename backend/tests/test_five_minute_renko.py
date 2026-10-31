"""Synthetic construction evidence, not independent TradingView feed parity."""

import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as DBSession

from app.broker.kite_ticker import TickerWorker
from app.db.models import Base, MarketCheckpoint, StoredBrick
from app.db.session import database_engine
from app.market.candles_5m import MarketCandle
from app.market.five_minute_renko import FiveMinuteCloseRenko
from app.market.persistence import (
    MarketPersistence,
    PersistenceError,
    brick_from,
    encode,
)
from app.market.renko_builder import RenkoBuilder
from app.market.warmup import Session, SessionCalendar

START = datetime.fromisoformat("2026-10-23T09:15:00+05:30")
CALENDAR = SessionCalendar(
    date(2026, 10, 23),
    date(2026, 10, 26),
    (
        Session(START, START.replace(hour=15, minute=30)),
        Session(START.replace(day=26), START.replace(day=26, hour=15, minute=30)),
    ),
)


def candle(i, price, *, start=START, partial=False):
    at = start + timedelta(minutes=i)
    p = Decimal(str(price))
    return MarketCandle(at, at + timedelta(minutes=1), p, p, p, p, None, None, partial)


def series(closes):
    return [candle(i * 5 + j, p) for i, p in enumerate(closes) for j in range(5)]


def builder():
    return FiveMinuteCloseRenko("50", "24000", CALENDAR)


def run(b, candles):
    return [brick for c in candles for brick in b.on_candle(c)]


def test_completed_five_minute_closes_only_and_known_wicks():
    b = builder()
    # Seed24000; up to24100; opposite swing24020 cannot reverse; next up has
    # low24020. Later residual24275 becomes the reversal brick's high wick.
    bars = series([24000, 24100, 24020, 24150, 24275, 24150])
    out = run(b, bars)
    assert [(x.open, x.close) for x in out] == [
        (24000, 24050),
        (24050, 24100),
        (24100, 24150),
        (24150, 24200),
        (24200, 24250),
        (24200, 24150),
    ]
    assert out[2].low == Decimal(24020)
    assert out[-1].high == Decimal(24275)
    assert all(x.ts.minute % 5 == 0 for x in out)
    assert [x.index for x in out] == list(range(6))
    assert not b.gap_detected


def test_intra_period_closes_and_candle_highs_do_not_create_wicks():
    b = builder()
    bars = series([24000, 24100, 24150])
    bars[6] = replace(candle(6, 23000), high=Decimal(29000))
    out = run(b, bars)
    assert len(out) == 3
    assert all(
        x.high == max(x.open, x.close) and x.low == min(x.open, x.close) for x in out
    )


@pytest.mark.parametrize("cut", range(1, 30))
def test_restart_at_each_minute_matches_uninterrupted_history(cut):
    bars = series([24000, 24100, 24020, 24150, 24275, 24150])
    expected_builder = builder()
    expected = run(expected_builder, bars)
    b = builder()
    before = run(b, bars[:cut])
    resumed = builder()
    resumed.restore_snapshot(json.loads(encode(b.snapshot())))
    assert before + run(resumed, bars[cut:]) == expected
    assert encode(resumed.snapshot()) == encode(expected_builder.snapshot())


@pytest.mark.parametrize("problem", ["missing", "partial", "midperiod"])
def test_incomplete_period_is_not_seeded_and_gap_survives_restart(problem):
    b = builder()
    bars = series([24000, 24100])
    if problem == "missing":
        del bars[2]
    elif problem == "midperiod":
        bars = bars[2:]
    else:
        bars[2] = replace(bars[2], partial=True)
    assert run(b, bars) == []  # only second complete period can seed
    assert b.gap_detected and b.index == 0
    resumed = builder()
    resumed.restore_snapshot(json.loads(encode(b.snapshot())))
    assert resumed.gap_detected


def test_overnight_calendar_continuity_without_fabricating_bars():
    b = builder()
    run(
        b, [candle(i, 24000, start=START.replace(hour=15, minute=25)) for i in range(5)]
    )
    out = run(b, [candle(i, 24100, start=START.replace(day=26)) for i in range(5)])
    assert len(out) == 2 and not b.gap_detected


@pytest.mark.parametrize(
    "damage", ["duplicate", "backward", "naive", "outside", "ohlc"]
)
def test_invalid_source_is_atomic(damage):
    b = builder()
    b.on_candle(candle(0, 24000))
    bad = {
        "duplicate": candle(0, 24100),
        "backward": candle(-1, 24100),
        "naive": replace(candle(1, 24000), time=START.replace(tzinfo=None)),
        "outside": candle(0, 24000, start=START.replace(hour=8)),
        "ohlc": replace(candle(1, 24000), high=Decimal(1)),
    }[damage]
    before = encode(b.snapshot())
    with pytest.raises(ValueError):
        b.on_candle(bad)
    assert encode(b.snapshot()) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("minute_count", True),
        ("minute_count", 5),
        ("complete", 0),
        ("close", "NaN"),
        ("bucket", "2026-10-23T09:16:00+05:30"),
        ("next_index", 99),
        ("excursion_low", None),
    ],
)
def test_corrupt_checkpoint_is_rejected_atomically(field, value):
    b = builder()
    run(b, series([24000]))
    b.on_candle(candle(5, 24020))
    before = encode(b.snapshot())
    data = json.loads(before)
    data[field] = value
    with pytest.raises(ValueError):
        b.restore_snapshot(data)
    assert encode(b.snapshot()) == before


def test_unfinished_period_is_never_flushed_and_price_bypass_rejected():
    b = builder()
    assert run(b, series([24000])[:4]) == []
    assert b.last is None and b.minute_count == 4
    with pytest.raises(ValueError, match="candles"):
        b.on_price(25000, START)


def test_transaction_copy_shares_frozen_calendar_but_not_mutable_state():
    b = builder()
    b.on_candle(candle(0, 24000))
    copied = b.clone()
    assert copied.calendar is b.calendar
    copied.on_candle(candle(1, 24100))
    assert copied.minute_count == 2 and b.minute_count == 1


def test_nonpositive_grid_seed_cannot_create_unrestorable_checkpoint():
    b = FiveMinuteCloseRenko("50", "0", CALENDAR)
    bars = series([1])
    run(b, bars[:4])
    before = encode(b.snapshot())
    with pytest.raises(ValueError, match="positive Renko seed"):
        b.on_candle(bars[4])
    assert encode(b.snapshot()) == before


@settings(max_examples=25, deadline=None)
@given(st.lists(st.integers(23000, 25000), min_size=2, max_size=25))
def test_body_grid_matches_close_reference_and_wicks_have_correct_direction(prices):
    b = builder()
    actual = run(b, series(prices))
    reference = RenkoBuilder(50, 24000)
    expected = [
        x
        for i, p in enumerate(prices)
        for x in reference.on_price(p, START + timedelta(minutes=5 * (i + 1)))
    ]
    assert [(x.open, x.close, x.ts) for x in actual] == [
        (x.open, x.close, x.ts) for x in expected
    ]
    for x in actual:
        if x.direction == 1:
            assert x.high == x.close
            assert x.low == x.open or 50 < x.open - x.low < 100
        else:
            assert x.low == x.close
            assert x.high == x.open or 50 < x.high - x.open < 100


def test_sqlite_restart_rollback_and_old_profile_fence(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'five.db').as_posix()}")
    Base.metadata.create_all(engine)

    def store():
        return MarketPersistence(
            engine,
            "five",
            111,
            222,
            box=50,
            anchor=24000,
            source_minutes=5,
            calendar=CALENDAR,
        )

    def append(worker, c):
        worker.closed_candles[111].append(c)
        worker.candle_counts[111] += 1
        worker.persistence.save(worker)

    try:
        first_store = store()
        first = TickerWorker(None, 111, 222, persistence=first_store, calendar=CALENDAR)
        bars = series([24000, 24100, 24020, 24150])
        for c in bars[:13]:
            append(first, c)
        resumed_store = store()
        resumed = TickerWorker(
            None, 111, 222, persistence=resumed_store, calendar=CALENDAR
        )
        assert isinstance(resumed_store.renko, FiveMinuteCloseRenko)
        assert resumed_store.renko.minute_count == 3
        assert resumed.gap_required  # downtime is not readiness
        before = encode(resumed_store.renko.snapshot())
        with patch.object(
            engine.dialect,
            "do_commit",
            side_effect=OperationalError("", {}, Exception()),
        ):
            with pytest.raises(PersistenceError):
                append(resumed, bars[13])
        assert encode(resumed_store.renko.snapshot()) == before
        resumed_store.save(resumed)  # exact buffered minute retry
        for c in bars[14:]:
            append(resumed, c)
        with DBSession(engine) as db:
            actual = [
                brick_from(json.loads(r.payload))
                for r in db.scalars(
                    select(StoredBrick)
                    .where(StoredBrick.stream == "five")
                    .order_by(StoredBrick.index)
                )
            ]
            config = json.loads(db.get(MarketCheckpoint, "five").configuration)
        assert actual == run(builder(), bars)
        assert config["version"] == 2 and config["source_minutes"] == 5
        assert actual[-1].low == 24020
        with pytest.raises(PersistenceError, match="configuration"):
            TickerWorker(
                None,
                111,
                222,
                persistence=MarketPersistence(
                    engine, "five", 111, 222, box=50, anchor=24000
                ),
            )
    finally:
        engine.dispose()
