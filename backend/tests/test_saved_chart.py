"""Stopped display uses the exact saved source, never recomputes signals."""

import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.api.domain_service import DomainService
from app.api.event_hub import EventHub
from app.api.live_service import LiveService
from app.config import Settings
from app.db.models import Base, Instrument, MarketCheckpoint, StoredBrick
from app.db.session import database_engine
from app.indicator.chart_history import publish_chart_history
from app.indicator.persistence import IndicatorRepository
from app.indicator.settings import IndicatorSettings
from app.market.persistence import MarketPersistence, encode
from app.market.renko_builder import IST, Brick
from app.market.service import MarketService


@pytest.fixture
def saved(tmp_path):
    settings = Settings(
        _env_file=None,
        local_ui_enabled=True,
        renko_anchor=100,
        renko_box=50,
        renko_source_minutes=1,
        market_stream="saved",
        market_service_enabled=False,
        database_url=f"sqlite:///{(tmp_path / 'saved.db').as_posix()}",
    )
    engine = database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    at = datetime(2026, 10, 23, 11, tzinfo=IST)
    stream = "saved:0123456789abcdef"
    store = MarketPersistence(engine, stream, 111, 222, box=50, anchor=100)
    bricks = [
        Brick(i, Decimal(100 + i * 50), Decimal(150 + i * 50), 1, at) for i in range(4)
    ]
    with Session(engine) as db, db.begin():
        db.add(
            Instrument(
                exchange="NSE",
                tradingsymbol="NIFTY 50",
                instrument_token=111,
                name="NIFTY",
                expiry=None,
                strike=0,
                tick_size=Decimal(".05"),
                lot_size=1,
                instrument_type="INDEX",
                segment="INDICES",
            )
        )
        db.add(
            MarketCheckpoint(
                stream=stream,
                revision=1,
                configuration=store.configuration,
                state=encode(dict(next_index=4, last=asdict(bricks[-1]))),
            )
        )
        db.add_all(
            [
                StoredBrick(stream=stream, index=b.index, payload=encode(asdict(b)))
                for b in bricks
            ]
        )
    repository = IndicatorRepository(
        engine, stream, IndicatorSettings(atrLen=2, rsiLen=2)
    )
    for brick in bricks:
        repository.process(brick)
    publish_chart_history(engine, stream)
    auth = Mock()
    market = MarketService(settings, auth, engine, Mock(), clock=lambda: at)
    domain = DomainService(engine, market, lambda: None, lambda: None)
    live = LiveService(market, engine, EventHub())
    live.domain_sample = domain.sample
    yield market, live, domain, stream
    auth.historical_data.assert_not_called()
    auth.create_ticker.assert_not_called()
    engine.dispose()


def test_saved_chart_restores_published_overlays_and_signal_source(saved):
    market, live, domain, stream = saved
    snap = live.sample()
    assert snap.stream == stream and snap.latest_brick.index == 3
    assert snap.context["historical_signals_available"] is True
    assert "signals" not in snap.unavailable and "indicators" not in snap.unavailable
    assert domain.sample()["signal_stream"] == stream
    page = live.bricks(stream, -1, 300, None)
    assert page.indicators_available and len(page.overlays) == 4
    assert not snap.entries_enabled and not snap.desired and snap.ticks == []
    assert market.worker is None


def test_config_change_and_tampered_saved_brick_are_not_displayed(saved):
    market, _, _, stream = saved
    market.settings.renko_box = 25
    assert market.cached_closed_chart() is None
    market.settings.renko_box = 50
    with Session(market.engine) as db, db.begin():
        row = db.get(StoredBrick, (stream, 3))
        payload = json.loads(row.payload)
        payload["close"] = "350"
        row.payload = encode(payload)
    assert market.cached_closed_chart() is None


def test_changed_indicator_results_do_not_restore_previous_signals(saved):
    from app.db.models import IndicatorResult

    market, live, _, stream = saved
    with Session(market.engine) as db, db.begin():
        result = db.get(IndicatorResult, (stream, 0))
        payload = json.loads(result.payload)
        payload["rsi"] = 99
        result.payload = encode(payload)
    snap = live.sample()
    assert snap.stream != stream
    assert {"indicators", "signals"} <= set(snap.unavailable)
    assert snap.signals == [] and not snap.entries_enabled
