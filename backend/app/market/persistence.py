"""Atomic market checkpoints; decimals are stored as exact JSON strings."""

import json
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import CursorResult, Engine, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import MarketCheckpoint, StoredBrick, StoredCandle
from app.market.candles_5m import CandleBuilder, MarketCandle
from app.market.renko_builder import Brick, RenkoBuilder

if TYPE_CHECKING:
    from app.broker.kite_ticker import TickerWorker


class PersistenceError(RuntimeError):
    pass


def encode(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True, allow_nan=False)


def candle_from(data: dict[str, Any]) -> MarketCandle:
    return MarketCandle(
        time=datetime.fromisoformat(data["time"]),
        end=datetime.fromisoformat(data["end"]),
        open=Decimal(data["open"]),
        high=Decimal(data["high"]),
        low=Decimal(data["low"]),
        close=Decimal(data["close"]),
        volume=Decimal(data["volume"]) if data["volume"] is not None else None,
        oi=Decimal(data["oi"]) if data["oi"] is not None else None,
        vwap=Decimal(data["vwap"]) if data["vwap"] is not None else None,
        partial=data["partial"],
        vwap_partial=data["vwap_partial"],
    )


def brick_from(data: dict[str, Any]) -> Brick:
    return Brick(
        data["index"],
        Decimal(data["open"]),
        Decimal(data["close"]),
        data["direction"],
        datetime.fromisoformat(data["ts"]),
        Decimal(data["volume"]),
    )


def builder_state(builder: CandleBuilder) -> dict[str, Any]:
    return {
        "current": asdict(builder.current) if builder.current is not None else None,
        "last_time": builder.last_time,
        "day": builder.day,
        "cumulative": builder.cumulative,
        "weighted": builder.weighted,
        "total_volume": builder.total_volume,
        "vwap_partial": builder.vwap_partial,
        "next_partial": builder._next_partial,
        "closed_until": builder._closed_until,
    }


def restore_builder(builder: CandleBuilder, data: dict[str, Any]) -> None:
    builder.current = candle_from(data["current"]) if data["current"] else None
    builder.last_time = (
        datetime.fromisoformat(data["last_time"]) if data["last_time"] else None
    )
    builder.day = date.fromisoformat(data["day"]) if data["day"] else None
    builder.cumulative = (
        Decimal(data["cumulative"]) if data["cumulative"] is not None else None
    )
    builder.weighted = Decimal(data["weighted"])
    builder.total_volume = Decimal(data["total_volume"])
    builder.vwap_partial = data["vwap_partial"]
    builder._next_partial = data["next_partial"]
    builder._closed_until = (
        datetime.fromisoformat(data["closed_until"]) if data["closed_until"] else None
    )


class MarketPersistence:
    def __init__(
        self,
        engine: Engine,
        stream: str,
        spot: int,
        future: int,
        *,
        box: float | str = 50,
        anchor: float | str,
    ) -> None:
        if not stream.strip() or len(stream) > 160:
            raise ValueError("Stream name must contain 1–160 characters")
        self.engine = engine
        self.stream = stream
        self.renko = RenkoBuilder(box, anchor)
        self.configuration = encode(
            {
                "version": 1,
                "spot": spot,
                "future": future,
                "box": str(self.renko.box.normalize()),
                "anchor": str(self.renko.anchor.normalize()),
                "mode": "minute_close",
            }
        )
        self.revision = 0
        self.counts = {spot: 0, future: 0}

    def snapshot(
        self, worker: "TickerWorker", renko: RenkoBuilder | None = None
    ) -> dict[str, Any]:
        builder = renko if renko is not None else self.renko
        return {
            "version": 1,
            "builders": {t: builder_state(b) for t, b in worker.candles.items()},
            "counts": worker.candle_counts.copy(),
            "gap": worker.gap_required,
            "last": asdict(builder.last) if builder.last is not None else None,
            "last_timestamp": builder.last_timestamp,
            "next_index": builder.index,
        }

    def restore(self, worker: "TickerWorker") -> bool:
        """Restore exact pre-shutdown state; caller must mark downtime as a gap."""
        config = json.loads(self.configuration)
        if worker.tokens != [config["spot"], config["future"]]:
            raise PersistenceError("Persistence tokens do not match this worker")
        try:
            with Session(self.engine) as db:
                checkpoint = db.get(MarketCheckpoint, self.stream)
                if checkpoint is None:
                    return False
                if checkpoint.configuration != self.configuration:
                    raise PersistenceError(
                        "Stream configuration changed; use a new stream or rebuild"
                    )
                data = json.loads(checkpoint.state)
                if data["version"] != 1:
                    raise ValueError("Unknown checkpoint version")
                for token in worker.tokens:
                    restore_builder(worker.candles[token], data["builders"][str(token)])
                    worker.candle_counts[token] = data["counts"][str(token)]
                    self.counts[token] = worker.candle_counts[token]
                    rows = db.scalars(
                        select(StoredCandle)
                        .where(
                            StoredCandle.stream == self.stream,
                            StoredCandle.token == token,
                        )
                        .order_by(StoredCandle.time.desc())
                        .limit(100)
                    ).all()
                    worker.closed_candles[token].extend(
                        candle_from(json.loads(row.payload)) for row in reversed(rows)
                    )
                worker.gap_required = data["gap"]
                self.renko.last = brick_from(data["last"]) if data["last"] else None
                self.renko.last_timestamp = (
                    datetime.fromisoformat(data["last_timestamp"])
                    if data["last_timestamp"]
                    else None
                )
                self.renko.index = data["next_index"]
                self.revision = checkpoint.revision
                return True
        except SQLAlchemyError:
            raise PersistenceError(
                "Market database unavailable; run uv run alembic upgrade head"
            ) from None
        except (KeyError, TypeError, ValueError):
            raise PersistenceError(
                "Market checkpoint is invalid; rebuild this stream"
            ) from None

    def save(self, worker: "TickerWorker") -> None:
        renko = deepcopy(self.renko)
        try:
            with Session(self.engine) as db, db.begin():
                for token in worker.tokens:
                    count = worker.candle_counts[token] - self.counts[token]
                    if count < 0 or count > len(worker.closed_candles[token]):
                        raise PersistenceError("Unpersisted candle buffer overflow")
                    candles = (
                        list(worker.closed_candles[token])[-count:] if count else []
                    )
                    for candle in candles:
                        db.add(
                            StoredCandle(
                                stream=self.stream,
                                token=token,
                                time=candle.time.astimezone(UTC).isoformat(),
                                payload=encode(asdict(candle)),
                            )
                        )
                        if token == worker.tokens[0]:
                            for brick in renko.on_price(candle.close, candle.end):
                                db.add(
                                    StoredBrick(
                                        stream=self.stream,
                                        index=brick.index,
                                        payload=encode(asdict(brick)),
                                    )
                                )
                state = encode(self.snapshot(worker, renko))
                if self.revision == 0:
                    db.add(
                        MarketCheckpoint(
                            stream=self.stream,
                            revision=1,
                            configuration=self.configuration,
                            state=state,
                        )
                    )
                else:
                    result = db.execute(
                        update(MarketCheckpoint)
                        .where(
                            MarketCheckpoint.stream == self.stream,
                            MarketCheckpoint.revision == self.revision,
                        )
                        .values(revision=self.revision + 1, state=state)
                    )
                    if cast(CursorResult[Any], result).rowcount != 1:
                        raise PersistenceError(
                            "Stream changed in another writer; stop duplicate monitors"
                        )
            self.revision += 1
            self.counts = worker.candle_counts.copy()
            self.renko = renko
        except SQLAlchemyError:
            raise PersistenceError(
                "Market checkpoint save failed; previous transaction retained"
            ) from None
