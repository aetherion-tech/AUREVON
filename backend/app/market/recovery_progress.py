"""Thread-safe, credential-free progress snapshots for recovery and handoff."""

from datetime import datetime
from threading import RLock
from typing import Literal

Phase = Literal[
    "idle",
    "planning",
    "downloading",
    "rebuilding",
    "committing",
    "validating",
    "draining",
    "complete",
    "failed",
]


class RecoveryProgress:
    def __init__(self) -> None:
        self._lock = RLock()
        self._phase: Phase = "idle"
        self._done = self._total = 0
        self._failure: str | None = None
        self._sources: dict[int, datetime] = {}
        self._quality_pending = True

    def begin(self) -> None:
        with self._lock:
            self._phase = "planning"
            self._done = self._total = 0
            self._failure = None
            self._quality_pending = True

    def stage(self, phase: Phase, *, done: int = 0, total: int = 0) -> None:
        if not 0 <= done <= total:
            raise ValueError("Progress must be bounded by its declared work")
        with self._lock:
            self._phase, self._done, self._total = phase, done, total

    def committed(self, sources: dict[int, datetime], *, quality_pending: bool) -> None:
        with self._lock:
            self._sources = dict(sources)
            self._phase = "complete"
            self._failure = None
            self._quality_pending = quality_pending

    def restore_sources(self, sources: dict[int, datetime]) -> None:
        """Recover committed diagnostics without granting readiness or success."""
        with self._lock:
            self._sources = dict(sources)

    def invalidate(self) -> None:
        with self._lock:
            self._quality_pending = True

    def failed(self, code: str) -> None:
        # Accept only fixed public codes, never exception messages or broker payloads.
        allowed = {
            "authentication_required",
            "source_unavailable",
            "persistence_failed",
            "invalid_scope",
            "recovery_busy",
            "handoff_failed",
            "cancelled",
            "unexpected_failure",
        }
        with self._lock:
            self._phase = "failed"
            self._failure = code if code in allowed else "unexpected_failure"
            self._quality_pending = True

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "phase": self._phase,
                "completed_ranges": self._done,
                "total_ranges": self._total,
                "last_successful_source_time": {
                    str(t): at.isoformat() for t, at in self._sources.items()
                },
                "failure_reason": self._failure,
                "quality_pending": self._quality_pending,
                "entries_enabled": False,
            }
