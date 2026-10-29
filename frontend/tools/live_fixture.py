"""Publish synthetic equal-time Renko/indicator history in the browser test DB."""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import MarketCheckpoint, StoredBrick
from app.indicator.chart_history import publish_chart_history
from app.indicator.persistence import IndicatorRepository
from app.indicator.settings import IndicatorSettings
from app.market.persistence import encode
from app.market.renko_builder import Brick


def seed_chart(engine, stream):
    pine = IndicatorSettings(atrLen=2, rsiLen=2, minGrade="Weak and above (all)")
    repository = IndicatorRepository(engine, stream, pine)
    series = [23900, 23950, 24000, 24050, 24000, 23950, 23900, 23850] * 82
    opening = datetime.now(timezone.utc).replace(
        hour=4, minute=0, second=0, microsecond=0
    )
    bricks = []
    for i in range(len(series) - 1):
        brick = Brick(
            i,
            Decimal(series[i]),
            Decimal(series[i + 1]),
            1 if series[i + 1] > series[i] else -1,
            opening + timedelta(seconds=i // 3),
        )
        repository.process(brick)
        bricks.append(brick)
    with Session(engine) as db, db.begin():
        db.add(
            MarketCheckpoint(
                stream=stream,
                revision=1,
                state="{}",
                configuration=encode(
                    dict(
                        spot=111,
                        future=222,
                        box="50",
                        anchor="23900",
                        mode="minute_close",
                    )
                ),
            )
        )
        db.add_all(
            [
                StoredBrick(stream=stream, index=b.index, payload=encode(asdict(b)))
                for b in bricks
            ]
        )
    publish_chart_history(engine, stream)
