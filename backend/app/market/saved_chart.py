"""Read-only matching managed history; never resurrects a feed/trading owner."""

import json
import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Instrument, MarketCheckpoint, StoredBrick
from app.indicator.chart_history import digest, overlays
from app.market.closed_history import ClosedChart
from app.market.exchange_calendar import ExchangeCalendar
from app.market.persistence import MarketPersistence, brick_from


def saved_chart(
    engine: Engine, settings: Settings, exchange: ExchangeCalendar, at: datetime
) -> ClosedChart | None:
    if settings.renko_anchor is None or settings.renko_mode != "minute_close":
        return None
    pattern = re.compile(
        re.escape(settings.market_stream) + r":[0-9a-f]{16}(?::5m-close-wicks-v2)?$"
    )
    with Session(engine) as db:
        spot = db.get(Instrument, ("NSE", "NIFTY 50"))
        if spot is None:
            return None
        checkpoints = db.scalars(
            select(MarketCheckpoint).where(
                MarketCheckpoint.stream.startswith(
                    settings.market_stream + ":", autoescape=True
                )
            )
        ).all()
        found = []
        for checkpoint in checkpoints:
            if pattern.fullmatch(checkpoint.stream) is None:
                continue
            try:
                config = json.loads(checkpoint.configuration)
                state = json.loads(checkpoint.state)
                rows = db.scalars(
                    select(StoredBrick)
                    .where(StoredBrick.stream == checkpoint.stream)
                    .order_by(StoredBrick.index)
                ).all()
                if not rows or [r.index for r in rows] != list(range(len(rows))):
                    continue
                bricks = [brick_from(json.loads(r.payload)) for r in rows]
                last = bricks[-1]
                if (
                    any(b.index != r.index or b.ts > at for b, r in zip(bricks, rows))
                    or any(a.ts > b.ts for a, b in zip(bricks, bricks[1:]))
                    or state["next_index"] != len(rows)
                    or brick_from(state["last"]) != last
                    or config["spot"] != spot.instrument_token
                    or type(config["future"]) is not int
                    or config["future"] <= 0
                    or config["future"] == config["spot"]
                ):
                    continue
                expected = MarketPersistence(
                    engine,
                    checkpoint.stream,
                    config["spot"],
                    config["future"],
                    box=settings.renko_box,
                    anchor=settings.renko_anchor,
                    source_minutes=settings.renko_source_minutes,
                    calendar=exchange.year(last.ts.year)
                    if settings.renko_source_minutes == 5
                    else None,
                )
                if checkpoint.configuration != expected.configuration:
                    continue
                identity = dict(
                    stream=checkpoint.stream,
                    revision=checkpoint.revision,
                    configuration_id=digest(checkpoint.configuration),
                )
                try:
                    publication = overlays(db, identity, list(rows), None)
                    indicators = publication["indicators_available"]
                except (HTTPException, ValueError, KeyError, TypeError):
                    continue
                found.append(
                    ClosedChart(checkpoint.stream, last.ts, len(rows), indicators)
                )
            except (ValueError, KeyError, TypeError):
                continue
        return (
            max(found, key=lambda chart: (chart.as_of, chart.stream)) if found else None
        )
