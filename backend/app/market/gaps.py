"""Bounded, conservative uncertainty spans and calendar-aware recovery ranges."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Any, Literal

from app.market.warmup import HistoryRange, SessionCalendar, local_time

GapReason = Literal["disconnect", "reconnect", "overflow", "downtime"]
REASONS = {"disconnect", "reconnect", "overflow", "downtime"}


@dataclass(frozen=True)
class DataGap:
    token: int
    reason: GapReason
    start: datetime
    resume_after: datetime
    end: datetime | None = None


class GapTracker:
    """One envelope per token/reason; never silently forget unresolved gaps.

    Repeated incidents widen the envelope, so intact intervals between incidents
    may also be requested. This bounds metadata without dropping recovery work.
    SDK overflow callbacks may mark gaps concurrently with the event-loop worker.
    """

    def __init__(self, tokens: list[int]) -> None:
        self.tokens = tuple(tokens)
        self._gaps: dict[tuple[int, GapReason], DataGap] = {}
        self._lock = RLock()

    def mark(
        self,
        token: int,
        reason: GapReason,
        start: datetime,
        *,
        resume_after: datetime | None = None,
    ) -> None:
        start = local_time(start)
        resume_after = local_time(resume_after or start)
        if token not in self.tokens or reason not in REASONS:
            raise ValueError("Invalid gap token or reason")
        with self._lock:
            old = self._gaps.get((token, reason))
            self._gaps[token, reason] = DataGap(
                token,
                reason,
                min(start, old.start) if old else start,
                max(resume_after, old.resume_after) if old else resume_after,
            )

    def resume(self, token: int, at: datetime) -> None:
        at = local_time(at)
        with self._lock:
            for key, gap in self._gaps.items():
                if gap.token == token and gap.end is None and at >= gap.resume_after:
                    self._gaps[key] = DataGap(
                        token, gap.reason, gap.start, gap.resume_after, at
                    )

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(gap) for _, gap in sorted(self._gaps.items())]

    def absorb(self, other: "GapTracker") -> None:
        """Merge seed metadata without replacing the SDK callback's tracker."""
        for row in other.snapshot():
            key = row["token"], row["reason"]
            with self._lock:
                old = self._gaps.get(key)
                end = row["end"]
                if old is not None:
                    end = None if old.end is None or end is None else max(old.end, end)
                self._gaps[key] = DataGap(
                    row["token"],
                    row["reason"],
                    min(old.start, row["start"]) if old else row["start"],
                    max(old.resume_after, row["resume_after"])
                    if old
                    else row["resume_after"],
                    end,
                )

    def restore(self, rows: list[dict[str, Any]]) -> None:
        replacement: dict[tuple[int, GapReason], DataGap] = {}
        for row in rows:
            token, reason = row["token"], row["reason"]
            start = local_time(datetime.fromisoformat(str(row["start"])))
            resume_after = local_time(datetime.fromisoformat(str(row["resume_after"])))
            end = (
                local_time(datetime.fromisoformat(str(row["end"])))
                if row["end"] is not None
                else None
            )
            if (
                token not in self.tokens
                or reason not in REASONS
                or resume_after < start
                or (end is not None and end < resume_after)
                or (token, reason) in replacement
            ):
                raise ValueError("Invalid persisted gap")
            replacement[token, reason] = DataGap(
                token, reason, start, resume_after, end
            )
        with self._lock:
            self._gaps = replacement

    def ranges(
        self,
        token: int,
        minutes: Literal[1, 5],
        calendar: SessionCalendar,
        now: datetime,
    ) -> tuple[HistoryRange, ...]:
        """Include affected completed buckets, even the bucket receiving resume.

        Caller supplies actual sessions, including holidays/special sessions.
        Unfinished buckets wait for a later recovery pass; no bars are invented.
        """
        finish = local_time(now)
        if token not in self.tokens or minutes not in (1, 5):
            raise ValueError("Expected known token and one/five-minute interval")
        spans = [r for r in self.snapshot() if r["token"] == token]
        if not calendar.first_date <= finish.date() <= calendar.last_date or any(
            r["start"].date() < calendar.first_date for r in spans
        ):
            raise ValueError("Calendar does not cover unresolved gaps")
        step = timedelta(minutes=minutes)
        out: list[HistoryRange] = []
        for session in calendar.sessions:
            opening = local_time(session.opening)
            closing = min(local_time(session.closing), finish)
            affected = []
            for gap in spans:
                start, end = gap["start"], min(gap["end"] or finish, finish)
                first = max(opening, opening + ((start - opening) // step) * step)
                last = min(opening + ((end - opening) // step) * step, closing - step)
                # Closing can be mid-bucket: retain only aligned completed bars.
                last = opening + ((last - opening) // step) * step
                if first <= last:
                    affected.append((first, last))
            for first, last in sorted(affected):
                if out and out[-1].end + step >= first:
                    prior = out.pop()
                    first, last = prior.start, max(last, prior.end)
                out.append(
                    HistoryRange("minute" if minutes == 1 else "5minute", first, last)
                )
        return tuple(out)
