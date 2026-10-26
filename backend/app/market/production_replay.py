"""Replay recorded events through the production worker in an isolated stream."""

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.broker.kite_ticker import TickerWorker
from app.db.models import MarketCheckpoint, StoredBrick, StoredCandle
from app.market.persistence import MarketPersistence, PersistenceError
from app.market.warmup import SessionCalendar


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def replay_to_persistence(
    paths: list[Path], store: MarketPersistence, calendar: SessionCalendar
) -> dict[str, Any]:
    import json

    from app.tools.replay_ticks import replay_events

    with Session(store.engine) as db:
        if (
            db.get(MarketCheckpoint, store.stream) is not None
            or db.scalar(
                select(StoredCandle).where(StoredCandle.stream == store.stream).limit(1)
            )
            is not None
            or db.scalar(
                select(StoredBrick).where(StoredBrick.stream == store.stream).limit(1)
            )
            is not None
        ):
            raise PersistenceError("Replay requires a new isolated stream")
    config = json.loads(store.configuration)
    validator = TickerWorker(None, config["spot"], config["future"], calendar=calendar)
    for _ in replay_events(paths, worker=validator):
        pass
    provenance = [{"file": p.name, "sha256": _digest(p)} for p in paths]
    config = json.loads(store.configuration)
    worker = TickerWorker(None, config["spot"], config["future"], calendar=calendar)
    count = 0

    def committed(target: TickerWorker, event: dict[str, Any]) -> None:
        nonlocal count
        if event["kind"] == "checkpoint" and (
            any(event["checkpoint"]["counts"].values())
            or event["checkpoint"].get("last") is not None
        ):
            raise PersistenceError(
                "Nonempty seed requires its baseline; use a complete source"
            )
        store.metadata["replay"] = {
            "source_run": event["session"],
            "sequence": event["sequence"],
            "files": provenance,
            "entries_enabled": False,
        }
        store.save(target)
        count += 1

    for _ in replay_events(paths, worker=worker, on_event=committed):
        pass
    return {
        "events": count,
        "candles": worker.candle_counts.copy(),
        "bricks": store.renko.index,
        "source": provenance,
        "entries_enabled": False,
    }
