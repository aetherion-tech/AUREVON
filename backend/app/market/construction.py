"""One managed construction factory for cold history, recovery and live ownership."""

from typing import Any

from sqlalchemy import Engine

from app.config import Settings
from app.market.candles_5m import MarketCandle
from app.market.exchange_calendar import ExchangeCalendar
from app.market.five_minute_renko import FiveMinuteCloseRenko
from app.market.persistence import MarketPersistence
from app.market.renko_builder import Brick, RenkoBuilder
from app.market.warmup import SessionCalendar


def managed_store(
    engine: Engine,
    settings: Settings,
    stream: str,
    spot: int,
    future: int,
    calendar: SessionCalendar,
) -> MarketPersistence:
    if settings.renko_mode != "minute_close" or settings.renko_anchor is None:
        raise ValueError(
            "Managed construction requires minute_close and an explicit anchor"
        )
    # A rolling warm-up window changes daily; annual coverage does not. Calendar
    # edits/year rollover intentionally require an explicit new profile/rebuild.
    stable = (
        ExchangeCalendar(settings.market_calendar_dir).year(calendar.last_date.year)
        if settings.renko_source_minutes == 5
        else None
    )
    return MarketPersistence(
        engine,
        stream,
        spot,
        future,
        box=settings.renko_box,
        anchor=settings.renko_anchor,
        source_minutes=settings.renko_source_minutes,
        calendar=stable,
    )


def consume_spot(renko: RenkoBuilder, candle: MarketCandle) -> list[Brick]:
    return (
        renko.on_candle(candle)
        if isinstance(renko, FiveMinuteCloseRenko)
        else renko.on_price(candle.close, candle.end)
    )


def construction_state(renko: RenkoBuilder) -> dict[str, Any]:
    return (
        {
            "renko_pipeline": renko.snapshot(),
            "construction_gap_detected": renko.gap_detected,
        }
        if isinstance(renko, FiveMinuteCloseRenko)
        else {}
    )
