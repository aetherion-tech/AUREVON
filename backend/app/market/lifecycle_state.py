"""Local process ownership, durable lifecycle facts and bounded events."""

import json
import os
from collections import deque
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.models import MarketLifecycleState
from app.market.persistence import encode


class ProcessLease:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream: Any = None

    def acquire(self) -> None:
        if self.stream is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        try:
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                getattr(fcntl, "flock")(
                    stream.fileno(),
                    getattr(fcntl, "LOCK_EX") | getattr(fcntl, "LOCK_NB"),
                )
        except OSError:
            stream.close()
            raise RuntimeError("Another managed market owner is active") from None
        self.stream = stream

    def release(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


class LifecycleStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def read(self, key: str) -> dict[str, Any]:
        with Session(self.engine) as db:
            row = db.get(MarketLifecycleState, key)
            return json.loads(row.payload) if row else {}

    def write(self, key: str, payload: dict[str, Any]) -> None:
        with Session(self.engine) as db, db.begin():
            db.merge(MarketLifecycleState(key=key, payload=encode(payload)))


class MarketEvents:
    def __init__(self) -> None:
        self.run_id = uuid4().hex
        self.sequence = 0
        self.events: deque[dict[str, Any]] = deque(maxlen=200)
        self.last: dict[str, str] = {}

    def publish(self, kind: str, payload: dict[str, Any]) -> None:
        encoded = encode(payload)
        if self.last.get(kind) == encoded:
            return
        self.last[kind] = encoded
        self.sequence += 1
        self.events.append(
            {"sequence": self.sequence, "kind": kind, "payload": json.loads(encoded)}
        )

    def since(self, sequence: int = 0) -> dict[str, Any]:
        return {
            "events": [
                json.loads(encode(e)) for e in self.events if e["sequence"] > sequence
            ],
            "resync_required": bool(
                sequence > self.sequence
                or (self.events and sequence < self.events[0]["sequence"] - 1)
            ),
            "sequence": self.sequence,
            "run_id": self.run_id,
        }
