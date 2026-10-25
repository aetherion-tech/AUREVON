"""Pure historical range planning; calendar data is supplied, never inferred."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from app.broker.kite_auth import IST
from app.config import Settings


def local_time(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Planning timestamps must include a timezone")
    return value.astimezone(IST)


@dataclass(frozen=True)
class Session:
    opening: datetime
    closing: datetime

    def __post_init__(self) -> None:
        start, end = local_time(self.opening), local_time(self.closing)
        if (
            start.date() != end.date()
            or start >= end
            or start.second
            or start.microsecond
            or end.second
            or end.microsecond
            or start.minute % 5
            or end.minute % 5
        ):
            raise ValueError("Sessions must have same-day, five-minute aligned bounds")


@dataclass(frozen=True)
class SessionCalendar:
    """Absent dates within coverage are explicitly non-trading dates."""

    first_date: date
    last_date: date
    sessions: tuple[Session, ...]

    def __post_init__(self) -> None:
        days = [local_time(s.opening).date() for s in self.sessions]
        if (
            self.first_date > self.last_date
            or days != sorted(set(days))
            or any(not self.first_date <= d <= self.last_date for d in days)
        ):
            raise ValueError(
                "Invalid calendar coverage or unordered/duplicate sessions"
            )


@dataclass(frozen=True)
class CheckpointBoundaries:
    """Next unprocessed candle openings from a validated restored checkpoint.

    Use active candle opening when present, otherwise closed_until. Missing
    boundaries require an explicit rebuild, not an implicit cold-start fallback.
    """

    spot: datetime
    futures: datetime


@dataclass(frozen=True)
class HistoryRange:
    interval: Literal["minute", "5minute"]
    start: datetime
    end: datetime  # Inclusive candle opening time, matching historical.download.

    @property
    def completed_through(self) -> datetime:
        return self.end + timedelta(minutes=1 if self.interval == "minute" else 5)


@dataclass(frozen=True)
class WarmupPlan:
    mode: Literal["cold_start", "checkpoint_restart"]
    cutoff: datetime
    spot: tuple[HistoryRange, ...]
    futures: tuple[HistoryRange, ...]
    previous_session: date
    minimum_futures_bars: int = 21
    # Planning cannot establish brick-count sufficiency, parity or readiness.
    entries_enabled: Literal[False] = False


def plan_history(
    settings: Settings,
    calendar: SessionCalendar,
    now: datetime,
    checkpoint: CheckpointBoundaries | None = None,
) -> WarmupPlan:
    cutoff = local_time(now)
    if not calendar.first_date <= cutoff.date() <= calendar.last_date:
        raise ValueError("Calendar does not cover the planning cutoff")
    prior = [s for s in calendar.sessions if local_time(s.closing) <= cutoff]
    if not prior:
        raise ValueError("Calendar lacks a completed session for daily context")
    previous = [s for s in prior if local_time(s.opening).date() < cutoff.date()]
    if not previous:
        raise ValueError("Calendar lacks previous-day daily context")
    if checkpoint is None:
        if len(prior) < settings.warmup_lookback_trading_days:
            raise ValueError("Calendar lacks the configured trading-session lookback")
        start = local_time(prior[-settings.warmup_lookback_trading_days].opening)
        spot_start = futures_start = start
    else:
        spot_start, futures_start = map(
            local_time, (checkpoint.spot, checkpoint.futures)
        )
        for boundary, minutes in ((spot_start, 1), (futures_start, 5)):
            if boundary > cutoff:
                raise ValueError("Checkpoint boundary is after the planning cutoff")
            if cutoff - boundary > timedelta(days=settings.recovery_max_gap_days):
                raise ValueError("Checkpoint gap exceeds automatic recovery limit")
            if boundary.date() < calendar.first_date:
                raise ValueError("Calendar does not cover the checkpoint gap")
            if boundary.second or boundary.microsecond or boundary.minute % minutes:
                raise ValueError("Checkpoint boundary is not candle-aligned")
        # Fetch current-session futures context for VWAP without changing the
        # checkpoint's application boundary. Import/merge must remain idempotent.
        current = next(
            (
                s
                for s in calendar.sessions
                if local_time(s.opening).date() == cutoff.date()
            ),
            None,
        )
        if current is not None and local_time(current.opening) <= cutoff:
            futures_start = min(futures_start, local_time(current.opening))

    def ranges(start: datetime, minutes: Literal[1, 5]) -> tuple[HistoryRange, ...]:
        result: list[HistoryRange] = []
        step = timedelta(minutes=minutes)
        for session in calendar.sessions:
            opening = local_time(session.opening)
            finish = min(local_time(session.closing), cutoff)
            count = (finish - opening) // step
            first = max(start, opening)
            # Both starts are aligned to exchange candle boundaries.
            end = opening + (count - 1) * step
            if count > 0 and first <= end:
                result.append(
                    HistoryRange("minute" if minutes == 1 else "5minute", first, end)
                )
        return tuple(result)

    spot, futures = ranges(spot_start, 1), ranges(futures_start, 5)
    if checkpoint is None:
        bars = sum((r.end - r.start) // timedelta(minutes=5) + 1 for r in futures)
        if bars < 21:
            raise ValueError("History lacks 21 futures bars for lagged volume average")
    return WarmupPlan(
        "cold_start" if checkpoint is None else "checkpoint_restart",
        cutoff,
        spot,
        futures,
        local_time(previous[-1].opening).date(),
    )
