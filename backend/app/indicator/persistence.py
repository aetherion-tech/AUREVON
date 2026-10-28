"""Transactional indicator replay processor with durable retry identity and fencing."""

import json
from dataclasses import asdict
from typing import Any

from sqlalchemy import CursorResult, Engine, update
from sqlalchemy.orm import Session

from app.db.models import IndicatorCheckpoint, IndicatorEvent, IndicatorResult
from app.indicator.settings import IndicatorSettings
from app.indicator.strategy import PineContext, PineEngine
from app.market.persistence import encode
from app.market.renko_builder import Brick


class IndicatorRepository:
    """One caller per stream; DB compare-and-swap prevents stale owner commits.

    No live-market subscriptions or strategy orders are started here. Successful
    return means checkpoint, candidates/results and events committed together.
    Identical retries return committed output; changed input under the same index
    is rejected. A lost/racing writer rolls back every inserted row.
    """

    def __init__(
        self, database: Engine, stream: str, settings: IndicatorSettings | None = None
    ) -> None:
        if not stream.strip() or len(stream) > 160:
            raise ValueError("indicator stream must contain 1–160 characters")
        self.database, self.stream, self.settings = (
            database,
            stream,
            settings or IndicatorSettings(),
        )

    def process(
        self, brick: Brick, context: PineContext | None = None
    ) -> dict[str, Any]:
        context = context or PineContext()
        context.validate(brick)
        identity = encode(
            {
                "brick": asdict(brick),
                "context": context.serializable(),
                "settings": self.settings.values,
            }
        )
        with Session(self.database) as db, db.begin():
            committed = db.get(IndicatorResult, (self.stream, brick.index))
            if committed:
                if committed.input != identity:
                    raise ValueError("committed indicator input identity changed")
                restored: dict[str, Any] = json.loads(committed.payload)
                return restored
            checkpoint = db.get(IndicatorCheckpoint, self.stream)
            current = (
                PineEngine.restore(
                    json.loads(checkpoint.payload), self.stream, self.settings
                )
                if checkpoint
                else PineEngine(self.stream, self.settings)
            )
            previous = current.base.last_index
            result = current.process(brick, context)
            payload = encode(current.snapshot())
            if checkpoint:
                changed = db.execute(
                    update(IndicatorCheckpoint)
                    .where(
                        IndicatorCheckpoint.stream == self.stream,
                        IndicatorCheckpoint.index == previous,
                        IndicatorCheckpoint.payload == checkpoint.payload,
                    )
                    .values(index=brick.index, payload=payload)
                )
                if not isinstance(changed, CursorResult) or changed.rowcount != 1:
                    raise RuntimeError("indicator checkpoint writer lost ownership")
            else:
                db.add(
                    IndicatorCheckpoint(
                        stream=self.stream, index=brick.index, payload=payload
                    )
                )
            db.add(
                IndicatorResult(
                    stream=self.stream,
                    index=brick.index,
                    input=identity,
                    payload=encode(result),
                )
            )
            records = [
                {"kind": "SIGNAL", **candidate} for candidate in result["signals"]
            ] + result["events"]
            for ordinal, event in enumerate(records):
                db.add(
                    IndicatorEvent(
                        stream=self.stream,
                        index=brick.index,
                        ordinal=ordinal,
                        kind=event["kind"],
                        payload=encode(event),
                    )
                )
            db.flush()
        return result
