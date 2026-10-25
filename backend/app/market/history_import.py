"""Build isolated candle/VWAP seeds from staged history; never mutate live workers."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import HistoricalContextCandle, HistoricalSpotCandle
from app.market.candles_5m import CandleBuilder, MarketCandle
from app.market.historical import parse_candle
from app.market.persistence import PersistenceError
from app.market.warmup import HistoryRange, SessionCalendar, WarmupPlan, local_time


@dataclass(frozen=True)
class HistoricalSeed:
    spot: CandleBuilder
    futures: CandleBuilder
    spot_candles: tuple[MarketCandle, ...]
    futures_candles: tuple[MarketCandle, ...]
    spot_missing: int
    futures_missing: int
    entries_enabled: Literal[False] = False


def build_historical_seed(
    engine: Engine,
    stream: str,
    spot_token: int,
    futures_identity: str,
    plan: WarmupPlan,
    calendar: SessionCalendar,
) -> HistoricalSeed:
    """Rebuild an isolated seed, making repeated reads deterministic.

    The caller keeps the exact futures identity from the source batch. This does
    not apply corrections, checkpoint state, Renko, queued ticks or readiness.
    """
    if not stream.strip() or spot_token <= 0 or not futures_identity.startswith("NFO:"):
        raise ValueError("Expected stream, positive spot token and exact NFO identity")
    cutoff = local_time(plan.cutoff)
    if not calendar.first_date <= cutoff.date() <= calendar.last_date:
        raise ValueError("Calendar does not cover seed cutoff")
    sessions = {local_time(s.opening).date(): s for s in calendar.sessions}

    def validate(ranges: tuple[HistoryRange, ...], minutes: int) -> None:
        previous: datetime | None = None
        for r in ranges:
            start, end = local_time(r.start), local_time(r.end)
            session = sessions.get(start.date())
            step = timedelta(minutes=minutes)
            if (
                r.interval != ("minute" if minutes == 1 else "5minute")
                or start > end
                or session is None
                or start < local_time(session.opening)
                or end + step > min(local_time(session.closing), cutoff)
                or (start - local_time(session.opening)) % step != timedelta(0)
                or (end - start) % step != timedelta(0)
                or (previous is not None and start <= previous)
            ):
                raise ValueError("Invalid historical seed ranges")
            previous = end

    validate(plan.spot, 1)
    validate(plan.futures, 5)
    try:
        with Session(engine) as db, db.begin():
            spot_rows = db.scalars(
                select(HistoricalSpotCandle)
                .where(
                    HistoricalSpotCandle.stream == stream,
                    HistoricalSpotCandle.token == spot_token,
                )
                .order_by(HistoricalSpotCandle.time)
            ).all()
            future_rows = db.scalars(
                select(HistoricalContextCandle)
                .where(
                    HistoricalContextCandle.stream == stream,
                    HistoricalContextCandle.identity == futures_identity,
                    HistoricalContextCandle.kind == "futures_5minute",
                )
                .order_by(HistoricalContextCandle.time)
            ).all()
            # Materialize inside the read transaction for a coherent source snapshot.
            raw_spot = [(r.time, r.completed_at, r.payload) for r in spot_rows]
            raw_futures = [(r.time, r.completed_at, r.payload) for r in future_rows]
    except SQLAlchemyError:
        raise PersistenceError(
            "History database unavailable; run uv run alembic upgrade head"
        ) from None

    def build(
        raw: list[tuple[str, str, str]],
        ranges: tuple[HistoryRange, ...],
        *,
        futures: bool,
    ) -> tuple[CandleBuilder, tuple[MarketCandle, ...], int]:
        minutes = 5 if futures else 1
        step = timedelta(minutes=minutes)
        builder = CandleBuilder(minutes, futures=futures)
        out: list[MarketCandle] = []
        expected = sum((r.end - r.start) // step + 1 for r in ranges)
        for stored_time, completed, payload in raw:
            stamp = local_time(datetime.fromisoformat(stored_time))
            if not any(r.start <= stamp <= r.end for r in ranges):
                continue
            data = json.loads(payload)
            row = [data[k] for k in ("time", "open", "high", "low", "close", "volume")]
            if futures:
                row.append(data["oi"])
            candle = parse_candle(row, oi=futures, allow_missing_oi=True)
            if (
                candle.time != stamp
                or datetime.fromisoformat(completed) != stamp + step
            ):
                raise ValueError(
                    "Historical source timestamps do not match stored boundaries"
                )
            session = sessions[stamp.date()]
            result = builder.import_completed(
                MarketCandle(
                    candle.time,
                    candle.time + step,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume if futures else None,
                    candle.oi if futures else None,
                    False,
                ),
                session_open=session.opening,
                session_close=session.closing,
                cutoff=cutoff,
            )
            out.append(result)
        missing = expected - len(out)
        # A gap in an older session must not taint a complete later session VWAP.
        latest_day = local_time(ranges[-1].start).date() if ranges else None
        latest_expected = sum(
            (r.end - r.start) // step + 1
            for r in ranges
            if local_time(r.start).date() == latest_day
        )
        latest_received = sum(c.time.date() == latest_day for c in out)
        if latest_received < latest_expected:
            builder.mark_gap()
        return builder, tuple(out), missing

    spot, spot_candles, spot_missing = build(raw_spot, plan.spot, futures=False)
    futures, futures_candles, futures_missing = build(
        raw_futures, plan.futures, futures=True
    )
    return HistoricalSeed(
        spot, futures, spot_candles, futures_candles, spot_missing, futures_missing
    )
