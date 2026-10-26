"""Fail-closed history validation and a monotonic post-handoff entry hold."""

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from time import monotonic
from typing import TYPE_CHECKING, Literal, cast

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import MarketCheckpoint, StoredBrick, StoredCandle
from app.market.candles_5m import CandleBuilder, MarketCandle
from app.market.gaps import GapTracker
from app.market.persistence import (
    PersistenceError,
    brick_from,
    builder_state,
    candle_from,
    encode,
)
from app.market.renko_builder import RenkoBuilder
from app.market.warmup import SessionCalendar, local_time, plan_history

if TYPE_CHECKING:
    from app.market.persistence import MarketPersistence


class ResumeGate:
    """Volatile eligibility only: restart and any failure require revalidation."""

    def __init__(self, delay: int, clock: Callable[[], float] = monotonic) -> None:
        if delay < 60:
            raise ValueError("Entry delay must be at least 60 seconds")
        self.delay = delay
        self.clock = clock
        self.started: float | None = None
        self.last: float | None = None

    def revoke(self) -> None:
        self.started = self.last = None

    def validated(self) -> None:
        self.started = self.last = self.clock()

    def eligible(self, *, healthy: bool) -> bool:
        now = self.clock()
        if not healthy or (self.last is not None and now < self.last):
            self.revoke()
            return False
        self.last = now
        return self.started is not None and now - self.started >= self.delay

    def snapshot(self, *, healthy: bool) -> dict[str, object]:
        now = self.clock()
        valid_clock = self.last is None or now >= self.last
        remaining = (
            max(0.0, self.delay - (now - self.started))
            if self.started is not None and valid_clock
            else None
        )
        state = (
            "awaiting_validation"
            if self.started is None
            else "blocked"
            if not healthy or not valid_clock
            else "entry_delay"
            if remaining
            else "hold_elapsed"
        )
        return {
            "state": state,
            "delay_seconds": self.delay,
            "remaining_seconds": remaining,
            "history_validated": self.started is not None and valid_clock,
            "external_gates_required": [
                "authentication",
                "session",
                "indicators",
                "execution_risk",
            ],
            "entries_enabled": False,
        }


def validate_history(
    store: "MarketPersistence",
    settings: Settings,
    calendar: SessionCalendar,
    at: datetime,
    boundaries: dict[int, datetime],
) -> int:
    try:
        return _validate_history(store, settings, calendar, local_time(at), boundaries)
    except (ValueError, KeyError, TypeError, OverflowError, SQLAlchemyError):
        raise PersistenceError(
            "History validation failed; retain sources and recover"
        ) from None


def _validate_history(
    store: "MarketPersistence",
    settings: Settings,
    calendar: SessionCalendar,
    at: "datetime",
    boundaries: dict[int, "datetime"],
) -> int:
    """Validate persisted source coverage and recomputed Renko before handoff.

    Returns the checked revision, never a reusable readiness authorization.
    Indicator/auth/feed/session gates remain independently required by entry callers.
    """
    if settings.renko_mode != "minute_close" or settings.renko_anchor is None:
        raise PersistenceError("Validated resumption requires minute-close mode")
    config = json.loads(store.configuration)
    expected = {
        "spot": config["spot"],
        "future": config["future"],
        "box": str(
            RenkoBuilder(settings.renko_box, settings.renko_anchor).box.normalize()
        ),
        "anchor": str(
            RenkoBuilder(settings.renko_box, settings.renko_anchor).anchor.normalize()
        ),
    }
    if any(config[key] != value for key, value in expected.items()):
        raise PersistenceError("Resume settings do not match checkpoint")
    plan = plan_history(settings, calendar, at)
    tokens = [config["spot"], config["future"]]
    if set(boundaries) != set(tokens):
        raise PersistenceError("Explicit spot and futures handoff boundaries required")
    with Session(store.engine) as db:
        checkpoint = db.get(MarketCheckpoint, store.stream)
        if checkpoint is None or checkpoint.configuration != store.configuration:
            raise PersistenceError("Validated checkpoint required")
        state = json.loads(checkpoint.state)
        rows = db.scalars(
            select(StoredCandle)
            .where(StoredCandle.stream == store.stream)
            .order_by(StoredCandle.time)
        ).all()
        candles: dict[int, dict[datetime, MarketCandle]] = {
            token: {} for token in tokens
        }
        rebuilt = {
            tokens[0]: CandleBuilder(1, futures=False),
            tokens[1]: CandleBuilder(5, futures=True),
        }
        renko = RenkoBuilder(settings.renko_box, settings.renko_anchor)
        bricks = []
        for row in rows:
            if row.token not in candles:
                raise PersistenceError("Unexpected candle token")
            candle = candle_from(json.loads(row.payload))
            if candle.partial or candle.vwap_partial:
                raise PersistenceError("History retains partial source flags")
            source_session = next(
                (
                    s
                    for s in calendar.sessions
                    if s.opening.date() == candle.time.date()
                ),
                None,
            )
            if source_session is None:
                raise PersistenceError("Calendar must cover all retained sources")
            rebuilt_candle = rebuilt[row.token].import_completed(
                candle,
                session_open=source_session.opening,
                session_close=source_session.closing,
                cutoff=at,
            )
            if rebuilt_candle != candle:
                raise PersistenceError("Candle/VWAP source state is inconsistent")
            candles[row.token][candle.time] = candle
            if row.token == tokens[0]:
                bricks.extend(renko.on_price(candle.close, candle.end))
        for token, ranges, minutes in (
            (tokens[0], plan.spot, 1),
            (tokens[1], plan.futures, 5),
        ):
            boundary = boundaries[token]
            if boundary.tzinfo is None or boundary.utcoffset() is None:
                raise PersistenceError("Timezone-aware boundaries required")
            # Exact unfinished-bucket fence: do not discard completed source intervals.
            expected_boundary: datetime | None
            session = next(
                (s for s in calendar.sessions if s.opening.date() == at.date()), None
            )
            if session is not None and session.opening <= at < session.closing:
                expected_boundary = session.opening + (
                    (at - session.opening) // timedelta(minutes=minutes)
                ) * timedelta(minutes=minutes)
            else:
                expected_boundary = ranges[-1].completed_through if ranges else None
            if boundary != expected_boundary:
                raise PersistenceError(
                    "Handoff does not match completed-history boundary"
                )
            for item in ranges:
                stamp = item.start
                while stamp <= item.end:
                    required = candles[token].get(stamp)
                    if (
                        required is None
                        or required.partial
                        or required.vwap_partial
                        or required.end != stamp + timedelta(minutes=minutes)
                        or (
                            token == tokens[1]
                            and (
                                required.oi is None
                                or required.volume is None
                                or required.vwap is None
                            )
                        )
                    ):
                        raise PersistenceError(
                            "History missing or unresolved quality flags"
                        )
                    stamp += timedelta(minutes=minutes)
            builder = state["builders"][str(token)]
            if builder["current"] is not None:
                raise PersistenceError(
                    "Active partial state requires recovery before handoff"
                )
            reference = json.loads(encode(builder_state(rebuilt[token])))
            if any(
                builder[key] != reference[key]
                for key in (
                    "day",
                    "weighted",
                    "total_volume",
                    "closed_until",
                )
            ):
                raise PersistenceError(
                    "Checkpoint builder/VWAP state does not match sources"
                )
            if state["counts"][str(token)] != len(candles[token]):
                raise PersistenceError("Checkpoint candle counts do not match sources")
        stored = db.scalars(
            select(StoredBrick)
            .where(StoredBrick.stream == store.stream)
            .order_by(StoredBrick.index)
        ).all()
        if (
            bricks != [brick_from(json.loads(b.payload)) for b in stored]
            or state["next_index"] != renko.index
            or (brick_from(state["last"]) if state["last"] else None) != renko.last
            or (
                datetime.fromisoformat(state["last_timestamp"])
                if state["last_timestamp"]
                else None
            )
            != renko.last_timestamp
        ):
            raise PersistenceError(
                "Derived Renko state does not match completed sources"
            )
        if renko.index == 0:
            raise PersistenceError("Insufficient Renko history; extend lookback")
        # Open incident markers can retire only for their proven completed prefix.
        # The fresh unfinished bucket remains partial; no tick order is inferred.
        for gap in state.get("gaps", []):
            if datetime.fromisoformat(gap["resume_after"]) > at:
                raise PersistenceError("Gap extends beyond the validation cutoff")
        tracker = GapTracker(tokens)
        tracker.restore(state.get("gaps", []))
        for token, minutes in ((tokens[0], 1), (tokens[1], 5)):
            for affected in tracker.ranges(
                token, cast(Literal[1, 5], minutes), calendar, at
            ):
                stamp = affected.start
                while stamp <= affected.end:
                    if stamp not in candles[token]:
                        raise PersistenceError("Gap source coverage is incomplete")
                    stamp += timedelta(minutes=minutes)
        recovery = state.get("recovery", {})
        if any(
            recovery.get(k, 0)
            for k in (
                "spot_missing",
                "futures_missing",
                "retained_partial",
                "oi_missing",
            )
        ):
            raise PersistenceError("Recovery still has unresolved quality flags")
        return checkpoint.revision
