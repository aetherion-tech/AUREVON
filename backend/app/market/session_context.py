"""Exchange-aligned daily and opening-range context from committed source bars."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import HistoricalContextCandle, StoredCandle
from app.market.lifecycle_state import LifecycleStore
from app.market.persistence import candle_from
from app.market.warmup import SessionCalendar, local_time


def session_context(
    engine: Engine, stream: str, spot: int, calendar: SessionCalendar, at: datetime
) -> dict[str, Any]:
    at = local_time(at)
    current = next(
        (s for s in calendar.sessions if s.opening.date() == at.date()), None
    )
    previous = [s for s in calendar.sessions if s.opening.date() < at.date()]
    prior = previous[-1] if previous else None
    with Session(engine) as db:
        rows = db.scalars(
            select(StoredCandle)
            .where(StoredCandle.stream == stream, StoredCandle.token == spot)
            .order_by(StoredCandle.time)
        ).all()
        candles = [candle_from(json.loads(r.payload)) for r in rows]
        today = [
            c
            for c in candles
            if current and current.opening <= c.time < c.end <= min(at, current.closing)
        ]
        yesterday = [
            c
            for c in candles
            if prior and prior.opening <= c.time < c.end <= prior.closing
        ]
        daily = db.scalars(
            select(HistoricalContextCandle).where(
                HistoricalContextCandle.stream == stream,
                HistoricalContextCandle.identity == "NSE:NIFTY 50",
                HistoricalContextCandle.kind == "spot_day",
            )
        ).all()
        prior_daily = next(
            (
                json.loads(r.payload)
                for r in daily
                if prior
                and local_time(datetime.fromisoformat(r.time)).date()
                == prior.opening.date()
                and datetime.fromisoformat(r.completed_at) <= at
            ),
            None,
        )
    expected = (
        max(0, int((min(at, current.closing) - current.opening).total_seconds() // 60))
        if current
        else 0
    )
    expected_stamps = (
        {current.opening + timedelta(minutes=i) for i in range(expected)}
        if current
        else set()
    )
    clean = {c.time for c in today} == expected_stamps and all(
        not c.partial for c in today
    )
    orb_end = current.opening + timedelta(minutes=15) if current else None
    orb = [c for c in today if orb_end and c.end <= orb_end]
    orb_ready = bool(
        orb_end and at >= orb_end and len(orb) == 15 and all(not c.partial for c in orb)
    )
    prior_complete = bool(
        prior
        and len(yesterday) == int((prior.closing - prior.opening).total_seconds() // 60)
        and all(not c.partial for c in yesterday)
    )
    previous_values = (
        {k: Decimal(str(prior_daily[k])) for k in ("close", "high", "low")}
        if prior_daily
        else {
            "close": yesterday[-1].close,
            "high": max(c.high for c in yesterday),
            "low": min(c.low for c in yesterday),
        }
        if prior_complete
        else {}
    )
    result = {
        "session": at.date().isoformat(),
        "previous_session": prior.opening.date().isoformat() if prior else None,
        "previous_close": previous_values.get("close"),
        "previous_high": previous_values.get("high"),
        "previous_low": previous_values.get("low"),
        "open": today[0].open
        if today and current and today[0].time == current.opening
        else None,
        "high": max((c.high for c in today), default=None),
        "low": min((c.low for c in today), default=None),
        "close": today[-1].close if today else None,
        "observed_through": today[-1].end if today else None,
        "partial": not clean,
        "missing_minutes": max(0, expected - len(today)),
        "opening_range": {
            "state": "unavailable"
            if not current
            else "complete"
            if orb_ready
            else "waiting"
            if current is not None and at < current.opening
            else "forming"
            if orb_end is not None and at < orb_end
            else "partial",
            "high": max((c.high for c in orb), default=None),
            "low": min((c.low for c in orb), default=None),
            "end": orb_end,
        },
        "entries_enabled": False,
    }
    LifecycleStore(engine).write(f"context:{stream}:{at.date()}", result)
    normalized: dict[str, Any] = json.loads(json.dumps(result, default=str))
    return normalized
