"""Stage futures and daily spot context without advancing live market state."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DBSession

from app.broker.kite_auth import IST, KiteAuth
from app.db.models import HistoricalContextBatch, HistoricalContextCandle, Instrument
from app.market.historical import Candle, download, parse_candle
from app.market.persistence import PersistenceError, encode
from app.market.warmup import SessionCalendar, WarmupPlan, local_time


@dataclass(frozen=True)
class ContextHistoryResult:
    batch_id: str
    futures_received: int
    futures_missing: int
    oi_missing: int
    daily_missing: int
    current_context_partial: bool


def fetch_context_history(
    auth: KiteAuth,
    engine: Engine,
    stream: str,
    futures_symbol: str,
    plan: WarmupPlan,
    calendar: SessionCalendar,
) -> ContextHistoryResult:
    """Use an explicit NIFTY contract, never infer a rollover or enable entries.

    Completed daily spot candles provide prior-session context. Today's evolving
    HLC is derived from completed minute candles only, through the plan cutoff.
    Every fetched source candle and the per-session context snapshot are audited.
    """
    if not stream.strip() or len(stream) > 160:
        raise ValueError("Expected stream name with 1-160 characters")
    cutoff = local_time(plan.cutoff)
    if not calendar.first_date <= cutoff.date() <= calendar.last_date:
        raise ValueError("Calendar does not cover context cutoff")
    sessions = {local_time(s.opening).date(): s for s in calendar.sessions}
    previous = [
        day
        for day, s in sessions.items()
        if day < cutoff.date() and local_time(s.closing) <= cutoff
    ]
    if not previous or previous[-1] != plan.previous_session:
        raise ValueError("Plan previous session does not match the supplied calendar")
    expected = 0
    last: datetime | None = None
    step = timedelta(minutes=5)
    for r in plan.futures:
        start, end = local_time(r.start), local_time(r.end)
        session = sessions.get(start.date())
        if (
            r.interval != "5minute"
            or start > end
            or end + step > cutoff
            or start.second
            or start.microsecond
            or end.second
            or end.microsecond
            or start.minute % 5
            or end.minute % 5
            or session is None
            or start < local_time(session.opening)
            or end + step > local_time(session.closing)
            or (last is not None and start <= last)
        ):
            raise ValueError(
                "Invalid completed futures range for the supplied calendar"
            )
        expected += (end - start) // step + 1
        last = end
    starts = [local_time(r.start).date() for r in (*plan.spot, *plan.futures)]
    first_day = min(starts, default=cutoff.date())
    prior_days = [day for day in sessions if day < first_day]
    if not prior_days:
        raise ValueError("Calendar needs a prior session before the context lookback")
    context_sessions = [
        s for day, s in sessions.items() if prior_days[-1] <= day <= cutoff.date()
    ]

    try:
        with DBSession(engine) as db:
            spot = db.get(Instrument, ("NSE", "NIFTY 50"))
            future = db.get(Instrument, ("NFO", futures_symbol))
            if (
                spot is None
                or future is None
                or future.name != "NIFTY"
                or future.instrument_type != "FUT"
                or future.expiry is None
            ):
                raise ValueError(
                    "Catalog must contain spot and the explicit NIFTY futures contract"
                )
            if future.expiry < cutoff.date():
                raise ValueError(
                    "Expired futures contract requires explicit historical identity"
                )
            spot_token, future_token = spot.instrument_token, future.instrument_token
            future_identity = f"NFO:{future.tradingsymbol}:{future.expiry.isoformat()}"
            contract = {
                "exchange": "NFO",
                "tradingsymbol": future.tradingsymbol,
                "expiry": future.expiry,
                "token": future_token,
                "lot_size": future.lot_size,
            }
    except SQLAlchemyError:
        raise PersistenceError(
            "Catalog database unavailable; run uv run alembic upgrade head"
        ) from None

    # Each tuple retains kind, contract identity, candle, and actual close time.
    sources: list[tuple[str, str, Candle, datetime]] = []
    futures: list[Candle] = []
    for r in plan.futures:
        candles = download(
            auth,
            future_token,
            r.start,
            r.end,
            interval="5minute",
            oi=True,
            now=cutoff,
            allow_missing_oi=True,
        )
        for future_candle in candles:
            if (
                future_candle.time.second
                or future_candle.time.microsecond
                or future_candle.time.minute % 5
            ):
                raise ValueError("Futures candle is not five-minute aligned")
            sources.append(
                (
                    "futures_5minute",
                    future_identity,
                    future_candle,
                    future_candle.time + step,
                )
            )
        futures.extend(candles)

    daily: dict[str, Candle] = {}
    contexts: list[dict[str, object]] = []
    daily_missing = 0
    current_partial = False
    for session in context_sessions:
        opening, closing = local_time(session.opening), local_time(session.closing)
        day = opening.date().isoformat()
        if opening > cutoff:
            continue
        candle: Candle | None = None
        partial = False
        observed: datetime | None = None
        missing_minutes = 0
        opening_known = True
        if closing <= cutoff:
            midnight = datetime.combine(opening.date(), time(), IST)
            data = auth.historical_data(
                spot_token,
                "day",
                midnight,
                midnight + timedelta(days=1) - timedelta(seconds=1),
            )
            rows = data.get("candles")
            if not isinstance(rows, list):
                raise ValueError("Invalid daily historical response")
            for row in rows:
                candidate = parse_candle(row, oi=False)
                if candidate.time.date() != opening.date():
                    raise ValueError("Daily candle outside requested session")
                # Canonical session opening avoids broker timestamp variants.
                candidate = Candle(
                    opening,
                    candidate.open,
                    candidate.high,
                    candidate.low,
                    candidate.close,
                    candidate.volume,
                    None,
                )
                if candle is not None and candle != candidate:
                    raise ValueError("Conflicting daily candles")
                candle = candidate
            if candle is not None:
                sources.append(("spot_day", "NSE:NIFTY 50", candle, closing))
                observed = closing
            else:
                daily_missing += 1
        else:
            end = cutoff.replace(second=0, microsecond=0) - timedelta(minutes=1)
            minutes = (
                download(auth, spot_token, opening, end, now=cutoff)
                if end >= opening
                else []
            )
            for item in minutes:
                if item.time.second or item.time.microsecond:
                    raise ValueError("Spot context candle is not minute aligned")
                sources.append(
                    (
                        "spot_minute",
                        "NSE:NIFTY 50",
                        item,
                        item.time + timedelta(minutes=1),
                    )
                )
            expected_minutes = max(0, (end - opening) // timedelta(minutes=1) + 1)
            missing_minutes = expected_minutes - len(minutes)
            partial = current_partial = True
            if minutes:
                opening_known = minutes[0].time == opening
                candle = Candle(
                    opening,
                    minutes[0].open,
                    max(c.high for c in minutes),
                    min(c.low for c in minutes),
                    minutes[-1].close,
                    sum((c.volume for c in minutes), Decimal(0)),
                    None,
                )
                observed = minutes[-1].time + timedelta(minutes=1)
        # Never substitute an older available close for the immediately prior session.
        index = context_sessions.index(session)
        required_previous = (
            local_time(context_sessions[index - 1].opening).date().isoformat()
            if index
            else None
        )
        previous_candle = daily.get(required_previous) if required_previous else None
        if opening.date() >= first_day:
            contexts.append(
                {
                    "session": day,
                    "previous_session": required_previous,
                    "previous_close": previous_candle.close
                    if previous_candle
                    else None,
                    "previous_high": previous_candle.high if previous_candle else None,
                    "previous_low": previous_candle.low if previous_candle else None,
                    "open": candle.open if candle and opening_known else None,
                    "high": candle.high if candle else None,
                    "low": candle.low if candle else None,
                    "close": candle.close if candle else None,
                    "partial": partial,
                    "previous_missing": previous_candle is None,
                    "current_missing": candle is None,
                    "missing_minutes": missing_minutes,
                    "observed_through": observed,
                }
            )
        if candle is not None and closing <= cutoff:
            daily[day] = candle

    batch_id = uuid4().hex
    missing_oi = sum(c.oi is None for c in futures)
    provenance = encode(
        {
            "version": 1,
            "source": "kite_historical",
            "contract": contract,
            "spot": {
                "exchange": "NSE",
                "tradingsymbol": "NIFTY 50",
                "token": spot_token,
            },
            "continuous": False,
            "oi_requested": True,
            "mode": plan.mode,
            "cutoff": cutoff,
            "fetched_at": datetime.now(UTC),
            "futures_ranges": [asdict(r) for r in plan.futures],
            "calendar_sessions": [asdict(s) for s in context_sessions],
            "futures_missing": expected - len(futures),
            "futures_expected": expected,
            "futures_received": len(futures),
            "oi_missing": missing_oi,
            "daily_missing": daily_missing,
            "daily_context": contexts,
        }
    )
    try:
        with DBSession(engine) as db, db.begin():
            db.add(
                HistoricalContextBatch(
                    id=batch_id, stream=stream, provenance=provenance
                )
            )
            db.flush()
            for kind, identity, candle, completed in sources:
                key = (stream, identity, kind, candle.time.astimezone(UTC).isoformat())
                saved = db.get(HistoricalContextCandle, key)
                payload = encode(asdict(candle))
                if saved is not None:
                    # Compare decimal strings by value, preserving stored precision.
                    old = json.loads(saved.payload)
                    row = [
                        old[k]
                        for k in ("time", "open", "high", "low", "close", "volume")
                    ]
                    if kind == "futures_5minute":
                        row.append(old["oi"])
                    old_candle = parse_candle(
                        row, oi=kind == "futures_5minute", allow_missing_oi=True
                    )
                    if (
                        old_candle != candle
                        or saved.completed_at != completed.astimezone(UTC).isoformat()
                    ):
                        raise PersistenceError(
                            "Conflicting context history; explicit correction required"
                        )
                    continue
                db.add(
                    HistoricalContextCandle(
                        stream=stream,
                        identity=identity,
                        kind=kind,
                        time=key[3],
                        completed_at=completed.astimezone(UTC).isoformat(),
                        payload=payload,
                        batch_id=batch_id,
                    )
                )
    except SQLAlchemyError:
        raise PersistenceError(
            "Context history save failed; previous data retained; "
            "run uv run alembic upgrade head if needed"
        ) from None
    return ContextHistoryResult(
        batch_id,
        len(futures),
        expected - len(futures),
        missing_oi,
        daily_missing,
        current_partial,
    )
