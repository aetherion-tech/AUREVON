"""Authenticated observation inbox and bounded comparison; no execution imports."""

import hashlib
import json
from collections import deque
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.api.security import DashboardSecurity
from app.config import Settings
from app.db.models import (
    IndicatorCheckpoint,
    IndicatorEvent,
    IndicatorResult,
    MarketCheckpoint,
    MarketLifecycleState,
    ShadowReceipt,
)
from app.market.persistence import encode


class ShadowEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(pattern=r"^[A-Za-z0-9:_-]{1,100}$")
    source_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    brick_index: int = Field(ge=0, strict=True)
    at: AwareDatetime
    kind: Literal["ENTRY", "EXIT"]
    family: Literal["CO", "DIV", "OT"]
    direction: Literal[-1, 1]
    trade_id: str = Field(min_length=1, max_length=100)


class ShadowStatus(BaseModel):
    enabled: bool
    stream: str
    source_id: str | None
    latest_index: int | None
    note: str = "Observation only; no alert can place or close a trade."


class ShadowComparison(BaseModel):
    source_id: str
    start: int
    end: int
    matched: int
    pending: int
    missing_tradingview: list[str]
    missing_backend: list[str]
    # A bounded window can describe mismatches; it never proves G2/G4.
    reference_verified: Literal[False] = False


def source(db: Session, stream: str) -> tuple[str, int]:
    checkpoint = db.get(IndicatorCheckpoint, stream)
    market = db.get(MarketCheckpoint, stream)
    if checkpoint is None or market is None:
        raise HTTPException(409)
    latest = db.get(IndicatorResult, (stream, checkpoint.index))
    if latest is None:
        raise HTTPException(409)
    settings = json.loads(latest.input)["settings"]
    identity = encode(
        {
            "stream": stream,
            "settings": settings,
            "market": json.loads(market.configuration),
        }
    )
    return hashlib.sha256(identity.encode()).hexdigest(), checkpoint.index


class ShadowService:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine, self.settings = engine, settings

    def status(self) -> ShadowStatus:
        identity, latest = None, None
        if self.settings.shadow_stream:
            with Session(self.engine) as db:
                try:
                    identity, latest = source(db, self.settings.shadow_stream)
                except HTTPException:
                    pass
        return ShadowStatus(
            enabled=(
                self.settings.shadow_ingestion_enabled
                and len(self.settings.shadow_webhook_secret.get_secret_value()) >= 32
                and bool(self.settings.shadow_stream)
            ),
            stream=self.settings.shadow_stream,
            source_id=identity,
            latest_index=latest,
        )

    def receive(self, event: ShadowEvent, now: datetime) -> dict[str, str]:
        if now.utcoffset() is None:
            raise ValueError("Aware receive clock required")
        # Delivery must be recent; historical exports belong in parity tooling.
        if not -30 <= (now - event.at).total_seconds() <= 300:
            raise HTTPException(422)
        stream = self.settings.shadow_stream
        payload = event.model_dump_json()
        key = hashlib.sha256((stream + ":" + event.event_id).encode()).hexdigest()
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            with Session(bind=connection) as db:
                expected, latest = source(db, stream)
                if expected != event.source_id or event.brick_index > latest + 2:
                    raise HTTPException(409)
                prior = db.get(ShadowReceipt, key)
                if prior is not None:
                    if prior.payload != payload:
                        raise HTTPException(409)
                    return {"id": key, "status": "duplicate"}
                # One durable counter per stream; no in-memory-only rate bypass.
                rate_key = "shadow-rate:" + hashlib.sha256(stream.encode()).hexdigest()
                rate = db.get(MarketLifecycleState, rate_key)
                minute = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
                state = json.loads(rate.payload) if rate else {}
                count = state.get("count", 0) if state.get("minute") == minute else 0
                if count >= 60:
                    raise HTTPException(429)
                db.merge(
                    MarketLifecycleState(
                        key=rate_key,
                        payload=encode({"minute": minute, "count": count + 1}),
                    )
                )
                db.add(
                    ShadowReceipt(
                        id=key,
                        stream=stream,
                        source_id=expected,
                        index=event.brick_index,
                        at=event.at.isoformat(),
                        received_at=now.astimezone(timezone.utc).isoformat(),
                        payload=payload,
                    )
                )
                db.flush()
                connection.commit()
        return {"id": key, "status": "recorded"}

    def compare(self, start: int, end: int) -> ShadowComparison:
        if end < start or end - start > 500:
            raise HTTPException(422)
        stream = self.settings.shadow_stream
        with Session(self.engine) as db:
            identity, latest = source(db, stream)
            if end > latest:
                raise HTTPException(409)
            # Include both window edges plus tolerance to avoid false edge gaps.
            backend = list(
                db.scalars(
                    select(IndicatorEvent)
                    .where(
                        IndicatorEvent.stream == stream,
                        IndicatorEvent.index >= max(0, start - 2),
                        IndicatorEvent.index <= end + 2,
                        IndicatorEvent.kind.in_(["ENTRY", "EXIT"]),
                    )
                    .order_by(IndicatorEvent.index, IndicatorEvent.ordinal)
                    .limit(2001)
                )
            )
            incoming = list(
                db.scalars(
                    select(ShadowReceipt)
                    .where(
                        ShadowReceipt.stream == stream,
                        ShadowReceipt.source_id == identity,
                        ShadowReceipt.index >= max(0, start - 2),
                        ShadowReceipt.index <= end + 2,
                    )
                    .order_by(ShadowReceipt.index, ShadowReceipt.id)
                    .limit(2001)
                )
            )
            if max(len(backend), len(incoming)) > 2000:
                raise HTTPException(413)

        def signature(item: dict[str, Any]) -> tuple[Any, ...]:
            typ = item.get("type")
            # Same grouping as original Pine f_fam2/f_code; HDIV shares DIV.
            family = (
                ("CO" if typ == "CORE" else "DIV" if typ in ("DIV", "HDIV") else "OT")
                if typ is not None
                else item["family"]
            )
            return (
                item["kind"],
                family,
                item["direction"],
                item["trade_id"],
            )

        left = [json.loads(row.payload) for row in backend]
        right = [
            ShadowEvent.model_validate_json(row.payload).model_dump()
            for row in incoming
        ]
        candidates = [
            [
                j
                for j, other in enumerate(incoming)
                if abs(row.index - other.index) <= 2
                and signature(left[i]) == signature(right[j])
            ]
            for i, row in enumerate(backend)
        ]
        # Maximum one-to-one matching. Two TV receipts cannot satisfy one event.
        matches: dict[int, int] = {}

        for root in range(len(backend)):
            queue = deque([root])
            parents: dict[int, tuple[int, int] | None] = {root: None}
            seen: set[int] = set()
            found = False
            while queue and not found:
                i = queue.popleft()
                for j in candidates[i]:
                    if j in seen:
                        continue
                    seen.add(j)
                    if j not in matches:
                        while True:
                            matches[j] = i
                            parent = parents[i]
                            if parent is None:
                                break
                            i, j = parent
                        found = True
                        break
                    previous = matches[j]
                    if previous not in parents:
                        parents[previous] = (i, j)
                        queue.append(previous)
        used = set(matches.values())
        missing_tv, missing_be = [], []
        pending = 0
        for i, row in enumerate(backend):
            if start <= row.index <= end and i not in used:
                if row.index + 2 >= latest:
                    pending += 1
                else:
                    missing_tv.append(f"{stream}:{row.index}:{row.ordinal}")
        for j, receipt in enumerate(incoming):
            if start <= receipt.index <= end and j not in matches:
                if receipt.index + 2 >= latest:
                    pending += 1
                else:
                    missing_be.append(
                        ShadowEvent.model_validate_json(receipt.payload).event_id
                    )
        return ShadowComparison(
            source_id=identity,
            start=start,
            end=end,
            matched=sum(start <= backend[i].index <= end for i in used),
            pending=pending,
            missing_tradingview=missing_tv,
            missing_backend=missing_be,
        )


def shadow_router(service: ShadowService, security: DashboardSecurity) -> APIRouter:
    router = APIRouter(tags=["TradingView shadow observations"])

    @router.post("/api/shadow/tv-alert")
    def receive(event: ShadowEvent) -> dict[str, str]:
        return service.receive(event, datetime.now(timezone.utc))

    @router.get("/api/shadow/status", dependencies=[Depends(security.require)])
    def status() -> ShadowStatus:
        return service.status()

    @router.get("/api/shadow/comparison", dependencies=[Depends(security.require)])
    def comparison(
        start: Annotated[int, Query(ge=0)],
        end: Annotated[int, Query(ge=0)],
    ) -> ShadowComparison:
        return service.compare(start, end)

    return router
