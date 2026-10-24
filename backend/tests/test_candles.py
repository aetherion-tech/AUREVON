"""Synthetic live candle sequences, not TradingView parity fixtures."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.market.candles_5m import CandleBuilder

START = datetime.fromisoformat("2026-10-23T09:15:00+05:30")


def feed(builder: CandleBuilder, seconds: int, price: int, volume: int = 100):
    return builder.on_tick(
        price,
        START + timedelta(seconds=seconds),
        cumulative_volume=volume,
        oi=500 + seconds,
    )


def test_futures_ohlc_volume_oi_and_hlc3_vwap() -> None:
    builder = CandleBuilder()
    assert feed(builder, 0, 100, 1000) == []
    feed(builder, 60, 110, 1010)
    feed(builder, 120, 90, 1030)
    feed(builder, 299, 105, 1040)
    first = feed(builder, 300, 120, 1050)[0]
    assert (first.open, first.high, first.low, first.close) == (100, 110, 90, 105)
    assert first.volume == 40
    assert first.oi == 799
    assert first.partial is True
    assert first.vwap == Decimal(305) / 3
    feed(builder, 599, 130, 1070)
    second = feed(builder, 600, 125, 1070)[0]
    assert second.volume == 30  # Includes cross-boundary delta of 10.
    assert second.partial is False
    expected = ((Decimal(305) / 3) * 40 + (Decimal(380) / 3) * 30) / 70
    assert second.vwap == expected
    assert second.vwap_partial is True  # No historical session warm-up yet.


def test_spot_minute_has_no_inferred_volume_and_closes_on_clock() -> None:
    builder = CandleBuilder(1, futures=False)
    feed(builder, 0, 24000)
    feed(builder, 58, 24050)
    assert builder.advance(START + timedelta(seconds=59)) == []
    candle = builder.advance(START + timedelta(minutes=1))[0]
    assert candle.time == START
    assert candle.end == START + timedelta(minutes=1)
    assert candle.volume is None and candle.oi is None and candle.vwap is None
    assert candle.close == 24050
    assert builder.advance(START + timedelta(minutes=2)) == []
    # A delayed packet cannot recreate a candle already closed by the clock.
    assert feed(builder, 59, 24075) == []
    assert builder.current is None


def test_gaps_missing_intervals_volume_reset_and_daily_reset() -> None:
    builder = CandleBuilder()
    feed(builder, 0, 100, 100)
    first = feed(builder, 900, 110, 150)
    assert len(first) == 1  # No synthetic 09:20 or 09:25 bars.
    assert builder.current.partial is True
    feed(builder, 901, 115, 10)  # Unexpected same-day counter decrease.
    assert builder.current.volume == 50
    assert builder.current.partial is True
    monday = START + timedelta(days=3)
    previous = builder.on_tick(200, monday, cumulative_volume=500, oi=99)[0]
    assert previous.end == START + timedelta(minutes=20)
    assert builder.current.volume == 0
    assert builder.total_volume == 0
    assert builder.current.oi == 99


def test_clock_staleness_marks_bar_and_next_bar_partial() -> None:
    builder = CandleBuilder()
    feed(builder, 0, 100)
    closed = builder.advance(START + timedelta(minutes=5))[0]
    assert closed.partial
    feed(builder, 301, 110, 110)
    assert builder.current.partial


def test_same_second_out_of_order_and_outside_session() -> None:
    builder = CandleBuilder()
    feed(builder, 60, 100)
    feed(builder, 60, 105)
    feed(builder, 59, 200)
    assert builder.current.close == 105
    before = builder.current
    builder.on_tick(200, START + timedelta(days=1), cumulative_volume=100)
    assert builder.current == before
    builder.on_tick(200, START.replace(hour=15, minute=30), cumulative_volume=100)
    assert builder.current == before


@pytest.mark.parametrize(
    "price,volume,oi",
    [("NaN", 100, 0), (0, 100, 0), (100, -1, 0), (100, None, 0), (100, 1, -1)],
)
def test_invalid_tick_does_not_mutate(price, volume, oi) -> None:
    builder = CandleBuilder()
    with pytest.raises(ValueError):
        builder.on_tick(price, START, cumulative_volume=volume, oi=oi)
    assert builder.current is None


def test_requires_timezone_and_supported_interval() -> None:
    with pytest.raises(ValueError):
        CandleBuilder(3)
    with pytest.raises(ValueError):
        CandleBuilder().on_tick(100, START.replace(tzinfo=None), cumulative_volume=10)
