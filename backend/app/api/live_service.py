"""Credential-free projection of the managed market worker and stored history."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from threading import Lock
from time import monotonic
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.api.event_hub import EventHub
from app.api.live_contracts import (
    AlertData,
    BrickData,
    BrickHistory,
    CandleData,
    CandleHistory,
    DataQuality,
    LiveSnapshot,
    SelectedInstrument,
    StatusData,
    TickData,
)
from app.api.schemas import ISTTimestamp, Page, Pagination
from app.broker.kite_auth import IST
from app.db.models import DashboardAlert, MarketCheckpoint, StoredBrick, StoredCandle
from app.market.persistence import encode
from app.market.service import MarketService


class LiveService:
    def __init__(self, market: MarketService, engine: Engine, hub: EventHub) -> None:
        self.market, self.engine, self.hub = market, engine, hub
        self.last_status = ""
        self.last_status_at = -1e10
        self.last_ticks: dict[int, str] = {}
        self.brick_cursor: tuple[str, int] | None = None
        self.conditions: set[str] = set()
        self.alert_lock = Lock()

    def sample(self) -> LiveSnapshot:
        # Called on the application event loop, with no awaits. The snapshot and
        # journal high-water mark are copied within one hub lock.
        with self.hub.lock:
            raw = self.market.status()
            worker = raw["worker"] or {}
            quality = DataQuality.model_validate(
                json.loads(
                    encode(
                        {k: worker[k] for k in DataQuality.model_fields if k in worker}
                    )
                )
            )
            selected = (
                SelectedInstrument.model_validate(raw["selected"])
                if raw["selected"]
                else None
            )
            stream = (
                worker.get("persisted_stream") or self.market.settings.market_stream
            )
            status = StatusData(
                state=raw["state"],
                desired=raw["desired"],
                selected=selected,
                quality=quality,
                recovery=raw["recovery"],
                context=json.loads(encode(raw["context"])),
            )
            encoded = status.model_dump_json()
            if encoded != self.last_status or monotonic() - self.last_status_at >= 5:
                self.hub.publish(status)
                self.last_status = encoded
                self.last_status_at = monotonic()
            ticks = []
            for token, tick in worker.get("latest", {}).items():
                value = TickData(
                    token=int(token),
                    price=Decimal(str(tick["price"])),
                    time=tick["time"],
                )
                ticks.append(value)
                if (
                    selected is not None
                    and value.token == selected.spot
                    and self.last_ticks.get(value.token) != value.model_dump_json()
                ):
                    if self.hub.publish(value) is not None:
                        self.last_ticks[value.token] = value.model_dump_json()
            configuration = encode(
                {
                    "box": str(self.market.settings.renko_box),
                    "anchor": str(self.market.settings.renko_anchor),
                    "mode": self.market.settings.renko_mode,
                }
            )
            latest_brick = (
                BrickData.model_validate(worker["last_renko_brick"])
                if worker.get("last_renko_brick")
                else None
            )
            with Session(self.engine) as db:
                checkpoint = db.get(MarketCheckpoint, stream)
                if checkpoint:
                    configuration = checkpoint.configuration
                # Emit every persisted brick, including multi-brick source closes.
                if self.brick_cursor is None or self.brick_cursor[0] != stream:
                    self.brick_cursor = (
                        stream,
                        latest_brick.index if latest_brick else 0,
                    )
                else:
                    rows = db.scalars(
                        select(StoredBrick)
                        .where(
                            StoredBrick.stream == stream,
                            StoredBrick.index > self.brick_cursor[1],
                        )
                        .order_by(StoredBrick.index)
                        .limit(257)
                    ).all()
                    for row in rows:
                        self.hub.publish(BrickData.model_validate_json(row.payload))
                        self.brick_cursor = (stream, row.index)
            self._quality_alerts(raw, quality)
            result = LiveSnapshot(
                run_id=self.hub.run_id,
                sequence=self.hub.sequence,
                at=datetime.now(IST),
                state=status.state,
                desired=status.desired,
                selected=selected,
                quality=quality,
                recovery=status.recovery,
                context=status.context,
                ticks=ticks,
                latest_brick=latest_brick,
                stream=stream,
                configuration_id=hashlib.sha256(configuration.encode()).hexdigest(),
            )
            self.hub.latest = result
            return result

    def _quality_alerts(self, raw: dict[str, Any], quality: DataQuality) -> None:
        conditions = set()
        if raw["state"] in ("login_required", "authentication_required"):
            conditions.add("authentication_required")
        if raw["recovery"].get("phase") == "failed":
            conditions.add("recovery_failed")
        if raw["worker"]:
            if quality.stale:
                conditions.add("feed_stale")
            if quality.gap_requires_replay:
                conditions.add("source_gap")
            if quality.clock_or_feed_delay:
                conditions.add("clock_or_feed_delay")
        for code in sorted(conditions - self.conditions):
            self.raise_alert(code)
        self.conditions = conditions

    def raise_alert(self, code: str) -> AlertData:
        # Only fixed public codes; never accept broker exception text.
        allowed = {
            "authentication_required",
            "recovery_failed",
            "feed_stale",
            "source_gap",
            "clock_or_feed_delay",
            "risk_reject",
            "reconciliation_mismatch",
        }
        if code not in allowed:
            raise ValueError("Unknown alert code")
        with self.alert_lock, Session(self.engine) as db, db.begin():
            existing = db.scalar(
                select(DashboardAlert)
                .where(
                    DashboardAlert.source_key == code,
                    DashboardAlert.acknowledged_at.is_(None),
                )
                .order_by(DashboardAlert.at.desc())
                .limit(1)
            )
            if existing:
                return self._alert(existing)
            row = DashboardAlert(
                id=uuid4().hex,
                source_key=code,
                level="critical" if code == "reconciliation_mismatch" else "warning",
                code=code,
                at=datetime.now(IST).isoformat(),
                acknowledged_at=None,
            )
            db.add(row)
            value = self._alert(row)
        self.hub.publish(value)
        return value

    @staticmethod
    def _alert(row: DashboardAlert) -> AlertData:
        return AlertData.model_validate(
            {k: getattr(row, k) for k in AlertData.model_fields}
        )

    def alerts(self, limit: int, offset: int) -> Page[AlertData]:
        with Session(self.engine) as db:
            rows = db.scalars(
                select(DashboardAlert)
                .order_by(DashboardAlert.at.desc(), DashboardAlert.id)
                .offset(offset)
                .limit(limit + 1)
            ).all()
            return Page(
                items=[self._alert(r) for r in rows[:limit]],
                pagination=Pagination(
                    limit=limit,
                    offset=offset,
                    next_offset=offset + limit if len(rows) > limit else None,
                ),
            )

    def acknowledge(self, identity: str) -> AlertData:
        with self.alert_lock, Session(self.engine) as db, db.begin():
            row = db.get(DashboardAlert, identity)
            if row is None:
                raise HTTPException(404)
            changed = row.acknowledged_at is None
            if changed:
                row.acknowledged_at = datetime.now(IST).isoformat()
            result = self._alert(row)
        if changed:
            self.hub.publish(result)
        return result

    def _identity(
        self, db: Session, stream: str, revision: int | None
    ) -> dict[str, Any]:
        checkpoint = db.get(MarketCheckpoint, stream)
        if checkpoint is None:
            raise HTTPException(404)
        if revision is not None and revision != checkpoint.revision:
            raise HTTPException(409)
        return {
            "stream": stream,
            "revision": checkpoint.revision,
            "configuration_id": hashlib.sha256(
                checkpoint.configuration.encode()
            ).hexdigest(),
            "configuration": json.loads(checkpoint.configuration),
        }

    def bricks(
        self, stream: str, after: int, limit: int, revision: int | None
    ) -> BrickHistory:
        with Session(self.engine) as db, db.begin():
            identity = self._identity(db, stream, revision)
            rows = db.scalars(
                select(StoredBrick)
                .where(StoredBrick.stream == stream, StoredBrick.index > after)
                .order_by(StoredBrick.index)
                .limit(limit + 1)
            ).all()
            return BrickHistory(
                **identity,
                items=[BrickData.model_validate_json(r.payload) for r in rows[:limit]],
                next_after=rows[limit - 1].index if len(rows) > limit else None,
            )

    def candles(
        self,
        stream: str,
        token: int,
        after: ISTTimestamp | None,
        limit: int,
        revision: int | None,
    ) -> CandleHistory:
        with Session(self.engine) as db, db.begin():
            identity = self._identity(db, stream, revision)
            if token not in (
                identity["configuration"]["spot"],
                identity["configuration"]["future"],
            ):
                raise HTTPException(422)
            query = select(StoredCandle).where(
                StoredCandle.stream == stream, StoredCandle.token == token
            )
            if after:
                query = query.where(StoredCandle.time > after.isoformat())
            rows = db.scalars(query.order_by(StoredCandle.time).limit(limit + 1)).all()
            return CandleHistory(
                **identity,
                token=token,
                items=[CandleData.model_validate_json(r.payload) for r in rows[:limit]],
                next_after=rows[limit - 1].time if len(rows) > limit else None,
            )
