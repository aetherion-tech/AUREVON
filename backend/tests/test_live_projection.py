"""Production worker projection retains multi-brick closes and source identity."""

from datetime import timedelta

from test_tick_recording import START, tick

from app.broker.kite_ticker import TickerWorker
from app.config import Settings
from app.db.models import Base
from app.main import create_app
from app.market.persistence import MarketPersistence
from app.market.service import SelectedContract


def test_live_projection_uses_real_tick_and_persisted_multi_bricks(tmp_path):
    settings = Settings(
        _env_file=None, database_url=f"sqlite:///{(tmp_path / 'project.db').as_posix()}"
    )
    app = create_app(settings)
    engine = app.state.database_engine
    Base.metadata.create_all(engine)
    market = app.state.market_service
    store = MarketPersistence(engine, "projection", 111, 222, box=10, anchor=100)
    worker = TickerWorker(
        None, 111, 222, persistence=store, clock=lambda: START + timedelta(minutes=5)
    )
    market.worker = worker
    market.selected = SelectedContract(111, 222, "TESTFUT", "2026-10-29", 65, "0.05")
    live = app.state.live_service
    try:
        baseline = live.sample()
        for minute, price in ((0, 100), (1, 150), (2, 200)):
            at = START + timedelta(minutes=minute)
            for token in worker.tokens:
                worker._accept(tick(token, at, price, 100 + minute * 10), at)
        snapshot = live.sample()
        assert [tick.token for tick in snapshot.ticks] == [111, 222]
        assert snapshot.quality.stale is True
        assert snapshot.latest_brick.index > 1
        assert snapshot.stream == "projection"
        events = live.hub.since(baseline.run_id, baseline.sequence)
        bricks = [event.payload.index for event in events if event.kind == "brick"]
        assert bricks == list(range(1, snapshot.latest_brick.index + 1))
        assert any(event.kind == "tick" for event in events)
        assert not snapshot.entries_enabled
    finally:
        market.worker = None
        engine.dispose()
