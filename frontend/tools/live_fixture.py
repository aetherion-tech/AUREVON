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
from app.market.renko_builder import Brick, WickBrick


def seed_closed_chart(engine, settings):
    """Synthetic broker adapter for closed-history browser tests only."""
    from unittest.mock import Mock

    from app.broker.kite_auth import IST, KiteAuth
    from app.db.models import Instrument
    from app.market.closed_history import load_closed_chart
    from app.market.exchange_calendar import ExchangeCalendar

    at = datetime(2026, 10, 24, 11, tzinfo=IST)
    settings.local_ui_enabled = True
    settings.renko_source_minutes = 5
    settings.warmup_lookback_trading_days = 1
    with Session(engine) as db, db.begin():
        db.add(
            Instrument(
                exchange="NSE",
                tradingsymbol="NIFTY 50",
                instrument_token=111,
                name="NIFTY",
                expiry=None,
                strike=0,
                tick_size=0.05,
                lot_size=65,
                instrument_type="EQ",
                segment="NSE",
            )
        )
    auth = Mock(spec=KiteAuth)

    def history(token, interval, start, end, **kwargs):
        assert token == 111 and interval == "minute"
        rows = []
        stamp = start
        while stamp <= end:
            i = int((stamp - stamp.replace(hour=9, minute=15)).total_seconds() // 60)
            price = str(23900 + ((i // 5) % 6) * 50)
            rows.append([stamp.isoformat(), price, price, price, price, "0"])
            stamp += timedelta(minutes=1)
        return {"candles": rows}

    auth.historical_data.side_effect = history
    result = load_closed_chart(
        auth,
        engine,
        settings,
        ExchangeCalendar(settings.market_calendar_dir),
        at,
        fetch=True,
    )
    assert result is not None
    return at


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
        if i == len(series) - 2:
            brick = WickBrick(
                i,
                brick.open,
                brick.close,
                brick.direction,
                brick.ts,
                wick_high=max(brick.open, brick.close) + Decimal(20),
                wick_low=min(brick.open, brick.close) - Decimal("12.5"),
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
                        source="isolated_synthetic_wick_replay",
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
