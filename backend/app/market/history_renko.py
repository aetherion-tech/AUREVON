"""Atomically initialize persistent minute-close Renko from staged history."""

from dataclasses import asdict, dataclass
from datetime import UTC
from typing import Literal

from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Instrument, MarketCheckpoint, StoredBrick, StoredCandle
from app.market.history_import import build_historical_seed
from app.market.persistence import (
    MarketPersistence,
    PersistenceError,
    builder_state,
    encode,
)
from app.market.renko_builder import Brick, RenkoBuilder
from app.market.warmup import SessionCalendar, WarmupPlan


@dataclass(frozen=True)
class HistoricalRenkoResult:
    renko: RenkoBuilder
    bricks: tuple[Brick, ...]
    revision: int
    imported: bool
    spot_missing: int
    futures_missing: int
    entries_enabled: Literal[False] = False


def rebuild_historical_renko(
    engine: Engine,
    settings: Settings,
    stream: str,
    spot_token: int,
    future_token: int,
    futures_identity: str,
    plan: WarmupPlan,
    calendar: SessionCalendar,
) -> HistoricalRenkoResult:
    """Initialize a cold stream, or verify an identical import without writes.

    Existing live checkpoints, changed configurations, changed source history and
    orphaned outputs require an explicit merge/rebuild workflow; never overwrite.
    Missing source ranges produce diagnostic bricks with a persistent gap flag.
    """
    if settings.renko_mode != "minute_close" or settings.renko_anchor is None:
        raise ValueError(
            "Historical Renko requires minute_close mode and an explicit anchor"
        )
    if plan.mode != "cold_start":
        raise ValueError(
            "Checkpoint recovery requires the historical/live merge workflow"
        )
    if min(spot_token, future_token) <= 0 or spot_token == future_token:
        raise ValueError("Expected distinct positive spot and futures tokens")
    store = MarketPersistence(
        engine,
        stream,
        spot_token,
        future_token,
        box=settings.renko_box,
        anchor=settings.renko_anchor,
    )
    try:
        with Session(engine) as db:
            spot = db.get(Instrument, ("NSE", "NIFTY 50"))
            future = db.scalars(
                select(Instrument).where(
                    Instrument.exchange == "NFO",
                    Instrument.name == "NIFTY",
                    Instrument.instrument_type == "FUT",
                    Instrument.instrument_token == future_token,
                )
            ).all()
            if (
                spot is None
                or spot.instrument_token != spot_token
                or len(future) != 1
                or future[0].expiry is None
                or futures_identity
                != f"NFO:{future[0].tradingsymbol}:{future[0].expiry.isoformat()}"
            ):
                raise ValueError(
                    "Historical import tokens must match the catalog identities"
                )
    except SQLAlchemyError:
        raise PersistenceError(
            "Catalog unavailable; run uv run alembic upgrade head"
        ) from None

    seed = build_historical_seed(
        engine, stream, spot_token, futures_identity, plan, calendar
    )
    if not seed.spot_candles:
        raise ValueError("No completed spot history available to seed Renko")
    bricks: list[Brick] = []
    for candle in seed.spot_candles:
        if (
            store.renko.last_timestamp is not None
            and candle.end <= store.renko.last_timestamp
        ):
            raise ValueError(
                "Historical Renko sources must have increasing close timestamps"
            )
        bricks.extend(store.renko.on_price(candle.close, candle.end))
    candles = {
        (token, candle.time.astimezone(UTC).isoformat()): encode(asdict(candle))
        for token, items in (
            (spot_token, seed.spot_candles),
            (future_token, seed.futures_candles),
        )
        for candle in items
    }
    brick_payloads = {brick.index: encode(asdict(brick)) for brick in bricks}
    state = encode(
        {
            "version": 1,
            "builders": {
                spot_token: builder_state(seed.spot),
                future_token: builder_state(seed.futures),
            },
            "counts": {
                spot_token: len(seed.spot_candles),
                future_token: len(seed.futures_candles),
            },
            "gap": True,
            "last": asdict(store.renko.last) if store.renko.last else None,
            "last_timestamp": store.renko.last_timestamp,
            "next_index": store.renko.index,
            "historical_import": {
                "version": 1,
                "plan": asdict(plan),
                "calendar": asdict(calendar),
                "futures_identity": futures_identity,
                "spot_missing": seed.spot_missing,
                "futures_missing": seed.futures_missing,
                "entries_enabled": False,
            },
        }
    )
    imported = False
    try:
        with Session(engine) as db, db.begin():
            checkpoint = db.get(MarketCheckpoint, stream)
            existing_candles = {
                (row.token, row.time): row.payload
                for row in db.scalars(
                    select(StoredCandle).where(StoredCandle.stream == stream)
                )
            }
            existing_bricks = {
                row.index: row.payload
                for row in db.scalars(
                    select(StoredBrick).where(StoredBrick.stream == stream)
                )
            }
            if checkpoint is not None:
                if (
                    checkpoint.revision != 1
                    or checkpoint.configuration != store.configuration
                    or checkpoint.state != state
                    or existing_candles != candles
                    or existing_bricks != brick_payloads
                ):
                    raise PersistenceError(
                        "Stream already contains different state; "
                        "explicit merge or rebuild required"
                    )
            else:
                if existing_candles or existing_bricks:
                    raise PersistenceError(
                        "Stream has outputs without a checkpoint; "
                        "explicit recovery required"
                    )
                for (token, stamp), payload in candles.items():
                    db.add(
                        StoredCandle(
                            stream=stream, token=token, time=stamp, payload=payload
                        )
                    )
                for index, payload in brick_payloads.items():
                    db.add(StoredBrick(stream=stream, index=index, payload=payload))
                db.add(
                    MarketCheckpoint(
                        stream=stream,
                        revision=1,
                        configuration=store.configuration,
                        state=state,
                    )
                )
                imported = True
    except SQLAlchemyError:
        raise PersistenceError(
            "Historical Renko save failed; previous data retained"
        ) from None
    return HistoricalRenkoResult(
        store.renko, tuple(bricks), 1, imported, seed.spot_missing, seed.futures_missing
    )
