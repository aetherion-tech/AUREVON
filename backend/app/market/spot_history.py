"""Fetch planned spot history and atomically stage it, without advancing state."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.broker.kite_auth import KiteAuth
from app.db.models import HistoricalSpotBatch, HistoricalSpotCandle, Instrument
from app.market.historical import Candle, download, parse_candle
from app.market.persistence import PersistenceError, encode
from app.market.warmup import WarmupPlan, local_time


@dataclass(frozen=True)
class SpotHistoryResult:
    batch_id: str
    received: int
    inserted: int
    missing_minutes: int


def fetch_spot_history(
    auth: KiteAuth,
    engine: Engine,
    stream: str,
    token: int,
    plan: WarmupPlan,
) -> SpotHistoryResult:
    """Require the catalog's NSE:NIFTY 50 token before making broker requests.

    All requests complete before one database transaction. Missing minutes are
    recorded, never synthesized; even a complete batch does not imply readiness.
    Conflicting saved history requires the later explicit correction workflow.
    """
    if not stream.strip() or len(stream) > 160 or token <= 0:
        raise ValueError(
            "Expected stream name (1-160 characters) and positive spot token"
        )
    cutoff = local_time(plan.cutoff)
    minute = timedelta(minutes=1)
    previous_end: datetime | None = None
    expected = 0
    for item in plan.spot:
        start, end = local_time(item.start), local_time(item.end)
        if (
            item.interval != "minute"
            or start > end
            or end + minute > cutoff
            or start.second
            or start.microsecond
            or end.second
            or end.microsecond
            or (previous_end is not None and start <= previous_end)
        ):
            raise ValueError("Spot plan must contain ordered, completed minute ranges")
        expected += (end - start) // minute + 1
        previous_end = end

    try:
        with Session(engine) as db:
            instrument = db.get(Instrument, ("NSE", "NIFTY 50"))
            if instrument is None or instrument.instrument_token != token:
                raise ValueError("Spot token must match NSE:NIFTY 50 in the catalog")
    except SQLAlchemyError:
        raise PersistenceError(
            "Instrument database unavailable; run uv run alembic upgrade head"
        ) from None

    candles: dict[datetime, Candle] = {}
    for item in plan.spot:
        for candle in download(auth, token, item.start, item.end, now=cutoff):
            if candle.time.second or candle.time.microsecond:
                raise ValueError("Historical spot candle is not minute-aligned")
            candles[candle.time] = candle

    batch_id = uuid4().hex
    provenance = encode(
        {
            "version": 1,
            "source": "kite_historical",
            "exchange": "NSE",
            "tradingsymbol": "NIFTY 50",
            "interval": "minute",
            "oi": False,
            "mode": plan.mode,
            "cutoff": cutoff,
            "fetched_at": datetime.now(UTC),
            "ranges": [asdict(item) for item in plan.spot],
            "expected_minutes": expected,
            "received_minutes": len(candles),
            "missing_minutes": expected - len(candles),
        }
    )
    inserted = 0
    try:
        with Session(engine) as db, db.begin():
            db.add(
                HistoricalSpotBatch(
                    id=batch_id, stream=stream, token=token, provenance=provenance
                )
            )
            db.flush()
            for candle in sorted(candles.values(), key=lambda c: c.time):
                opening = candle.time.astimezone(UTC).isoformat()
                completed_at = (candle.time + minute).astimezone(UTC).isoformat()
                payload = encode(asdict(candle))
                existing = db.get(HistoricalSpotCandle, (stream, token, opening))
                if existing is not None:
                    saved = json.loads(existing.payload)
                    saved_candle = parse_candle(
                        [
                            saved[key]
                            for key in (
                                "time",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                            )
                        ],
                        oi=False,
                    )
                    if saved_candle != candle or existing.completed_at != completed_at:
                        raise PersistenceError(
                            "Conflicting historical spot candle; "
                            "explicit correction required"
                        )
                    continue
                db.add(
                    HistoricalSpotCandle(
                        stream=stream,
                        token=token,
                        time=opening,
                        completed_at=completed_at,
                        payload=payload,
                        batch_id=batch_id,
                    )
                )
                inserted += 1
    except SQLAlchemyError:
        raise PersistenceError(
            "Historical spot save failed; previous data retained; "
            "run uv run alembic upgrade head if needed"
        ) from None
    return SpotHistoryResult(batch_id, len(candles), inserted, expected - len(candles))
