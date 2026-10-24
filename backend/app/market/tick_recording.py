"""Versioned, allowlisted market events, split by IST day and recording run."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.broker.kite_auth import IST


class RecordingError(RuntimeError):
    """A recording failure makes deterministic recovery unavailable."""


class TickRecorder:
    def __init__(self, directory: Path, spot: int, future: int) -> None:
        if spot <= 0 or future <= 0 or spot == future:
            raise ValueError("Distinct positive instrument tokens required")
        self.directory = directory / uuid4().hex
        self.spot = spot
        self.future = future
        self.sequence = 0

    def write(self, kind: str, at: datetime, payload: dict[str, Any]) -> None:
        """Flush each append containing normalized, allowlisted market fields."""
        if at.tzinfo is None:
            raise RecordingError("Recording requires timezone-aware timestamps")
        event = {
            "version": 1,
            "session": self.directory.name,
            "sequence": self.sequence,
            "spot_token": self.spot,
            "future_token": self.future,
            "kind": kind,
            "at": at.isoformat(),
            **payload,
        }
        path = self.directory / f"{at.astimezone(IST).date().isoformat()}.jsonl"
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(event, allow_nan=False, default=str) + "\n")
                stream.flush()
        except (OSError, ValueError, TypeError):
            raise RecordingError(
                "Cannot write tick recording; feed monitor stopped"
            ) from None
        self.sequence += 1
