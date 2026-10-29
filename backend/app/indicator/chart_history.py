"""Explicit validated replay publication, followed by bounded chart projections.

Publication verifies the complete stored indicator input prefix against committed
market bricks. It binds to one market revision and fingerprints every result.
Reads never recompute indicators, write bindings or attach a live producer.
"""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.api.chart_contracts import (
    ChartEvent,
    ChartPosition,
    IndicatorHistorySource,
    IndicatorOverlay,
)
from app.db.models import (
    IndicatorCheckpoint,
    IndicatorResult,
    MarketCheckpoint,
    StoredBrick,
)
from app.indicator.settings import IndicatorSettings
from app.indicator.strategy import PineContext, PineEngine
from app.market.persistence import brick_from, encode


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def result_id(row: IndicatorResult) -> str:
    return digest(encode({"input": row.input, "payload": row.payload}))


def point(
    row: IndicatorResult, brick: StoredBrick, settings_id: str
) -> IndicatorOverlay:
    source, output = json.loads(row.input), json.loads(row.payload)
    expected = brick_from(json.loads(brick.payload))
    context = dict(source["context"])
    if context.get("available_at") is not None:
        context["available_at"] = datetime.fromisoformat(context["available_at"])
    PineContext(**context).validate(expected)
    if (
        row.index != brick.index
        or row.stream != brick.stream
        or brick_from(source["brick"]) != expected
        or digest(encode(source["settings"])) != settings_id
        or output["index"] != row.index
        or output["schema_version"] != 1
        or output["mode"] != "INDICATOR_REPLAY"
        or output["entries_enabled"] is not False
        or output["time_ms"] != int(expected.ts.timestamp() * 1000)
        or Decimal(str(output["open"])) != expected.open
        or Decimal(str(output["close"])) != expected.close
    ):
        raise ValueError("chart source/input identity mismatch")
    return IndicatorOverlay(
        index=row.index,
        at=expected.ts,
        supertrend=output["supertrend"],
        supertrend_direction=output["direction"],
        rsi=output["rsi"],
        atr=output["atr"],
        bias_direction=output["bias_direction"],
        bias_score=output["bias_score"],
        bias_strong=output["bias_strong"],
        factors=output["factors"],
        support=output["support"],
        resistance=output["resistance"],
        up_trigger=output["up_trigger"],
        down_trigger=output["down_trigger"],
        up_probability=output["up_probability"],
        position=ChartPosition.model_validate(output["position"]),
        events=[
            ChartEvent.model_validate(
                {k: v for k, v in event.items() if k in ChartEvent.model_fields}
            )
            for event in output["events"]
        ],
    )


def publish_chart_history(engine: Engine, stream: str) -> IndicatorHistorySource:
    """Owner/replay operation, not an HTTP mutation or proof of TradingView parity.

    Called after committing a stable market/indicator replay prefix. Any market
    append/recovery or further indicator processing invalidates the publication.
    No schema migration: additive provenance is retained in indicator checkpoint
    JSON; the normal repository writer drops it when advancing that checkpoint.
    """
    if engine.dialect.name != "sqlite":
        raise ValueError("chart publication currently requires SQLite serialization")
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        with Session(bind=connection) as db:
            try:
                market = db.get(MarketCheckpoint, stream)
                checkpoint = db.get(IndicatorCheckpoint, stream)
                if market is None or checkpoint is None:
                    raise ValueError("market and indicator checkpoints required")
                snapshot = json.loads(checkpoint.payload)
                settings = IndicatorSettings(**snapshot["base"]["settings"])
                restored = PineEngine.restore(snapshot, stream, settings)
                if restored.base.last_index != checkpoint.index:
                    raise ValueError("indicator checkpoint index mismatch")
                configuration = json.loads(market.configuration)
                if Decimal(str(settings["boxSize"])) != Decimal(
                    str(configuration["box"])
                ):
                    raise ValueError("indicator and market brick sizes differ")
                settings_id = digest(encode(settings.values))
                manifest = {}
                rows = db.execute(
                    select(IndicatorResult, StoredBrick)
                    .outerjoin(
                        StoredBrick,
                        (StoredBrick.stream == IndicatorResult.stream)
                        & (StoredBrick.index == IndicatorResult.index),
                    )
                    .where(IndicatorResult.stream == stream)
                    .order_by(IndicatorResult.index)
                )
                for ordinal, (result, brick) in enumerate(rows.yield_per(256)):
                    if (
                        brick is None
                        or result.index != ordinal
                        or ordinal > checkpoint.index
                    ):
                        raise ValueError("incomplete or unordered chart history")
                    point(result, brick, settings_id)
                    manifest[str(result.index)] = result_id(result)
                if len(manifest) != checkpoint.index + 1:
                    raise ValueError("indicator history prefix missing")
                identity: dict[str, Any] = dict(
                    market_revision=market.revision,
                    configuration_id=digest(market.configuration),
                    settings_id=settings_id,
                    settings=settings.values,
                    last_index=checkpoint.index,
                )
                published = IndicatorHistorySource(
                    source_id=digest(encode({**identity, "manifest": manifest})),
                    **identity,
                )
                snapshot["chart_source"] = {
                    **published.model_dump(mode="json"),
                    "manifest": manifest,
                }
                checkpoint.payload = encode(snapshot)
                db.flush()
                connection.commit()
                return published
            except BaseException:
                connection.rollback()
                raise


def overlays(
    db: Session,
    identity: dict[str, Any],
    bricks: list[StoredBrick],
    expected_source: str | None,
) -> dict[str, Any]:
    indices = [r.index for r in bricks]
    unavailable = dict(
        indicators_available=False,
        overlays=[],
        indicator_source=None,
        missing_overlay_indices=indices,
        overlay_status="unavailable",
    )
    checkpoint = db.get(IndicatorCheckpoint, identity["stream"])
    try:
        snapshot = json.loads(checkpoint.payload) if checkpoint else {}
        if not isinstance(snapshot, dict):
            raise ValueError("invalid chart checkpoint")
        binding = snapshot.get("chart_source")
        if not binding:
            if expected_source is not None:
                raise HTTPException(409)
            return {**unavailable, "overlay_reason": "not_published"}
        if not isinstance(binding, dict):
            raise ValueError("invalid chart binding")
        source = IndicatorHistorySource.model_validate(
            {
                k: v
                for k, v in binding.items()
                if k in IndicatorHistorySource.model_fields
            }
        )
        if expected_source is not None and source.source_id != expected_source:
            raise HTTPException(409)
        if (
            source.market_revision != identity["revision"]
            or source.configuration_id != identity["configuration_id"]
        ):
            if expected_source is not None:
                raise HTTPException(409)
            return {**unavailable, "overlay_reason": "source_changed"}
        if checkpoint is None or checkpoint.index != source.last_index:
            if expected_source is not None:
                raise HTTPException(409)
            return {**unavailable, "overlay_reason": "indicator_advanced"}
        if source.settings_id != digest(encode(source.settings)):
            raise ValueError("chart settings hash mismatch")
        if not isinstance(binding.get("manifest"), dict):
            raise ValueError("invalid chart manifest")
        if len(binding["manifest"]) != source.last_index + 1:
            raise ValueError("incomplete chart manifest")
        found = (
            {
                r.index: r
                for r in db.scalars(
                    select(IndicatorResult).where(
                        IndicatorResult.stream == identity["stream"],
                        IndicatorResult.index.in_(indices),
                    )
                ).all()
            }
            if indices
            else {}
        )
        values, missing = [], []
        for brick in bricks:
            result = found.get(brick.index)
            expected = binding["manifest"].get(str(brick.index))
            if expected is None and brick.index > source.last_index:
                missing.append(brick.index)
                continue
            if result is None or expected != result_id(result):
                raise ValueError("published chart result changed or missing")
            values.append(point(result, brick, source.settings_id))
        return dict(
            indicators_available=True,
            indicator_source=source,
            overlays=values,
            missing_overlay_indices=missing,
            overlay_reason="none",
            overlay_status="empty"
            if not bricks
            else "partial"
            if missing
            else "complete",
        )
    except (ValueError, KeyError, TypeError, OverflowError):
        raise HTTPException(409) from None
