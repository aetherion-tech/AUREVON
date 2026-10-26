"""Sourced calendar, context, event and production replay acceptance."""

import json
from datetime import date, datetime, timedelta

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from test_tick_recording import START, tick

from alembic import command
from app.broker.kite_auth import IST
from app.broker.kite_ticker import TickerWorker
from app.config import BACKEND_DIR
from app.db.models import Base, MarketCheckpoint, StoredBrick, StoredCandle
from app.db.session import database_engine
from app.market.exchange_calendar import CalendarError, ExchangeCalendar
from app.market.lifecycle_state import LifecycleStore, MarketEvents, ProcessLease
from app.market.persistence import MarketPersistence
from app.market.production_replay import replay_to_persistence
from app.market.session_context import session_context
from app.market.tick_recording import TickRecorder
from app.market.warmup import Session as MarketSession
from app.market.warmup import SessionCalendar


def test_calendar_holidays_special_sessions_and_unknown_year(tmp_path):
    calendar = ExchangeCalendar(BACKEND_DIR / "app" / "market" / "calendars")
    assert calendar.session(datetime(2026, 1, 15, 10, tzinfo=IST)) is None
    assert calendar.session(datetime(2026, 10, 20, 10, tzinfo=IST)) is None
    assert calendar.session(datetime(2026, 10, 24, 10, tzinfo=IST)) is None
    assert calendar.session(datetime(2026, 2, 1, 10, tzinfo=IST)).opening.hour == 9
    special = calendar.session(datetime(2026, 11, 8, 15, tzinfo=IST))
    assert special.opening.hour == 14 and special.opening.minute == 20
    assert special.closing.hour == 15 and special.closing.minute == 30
    with pytest.raises(CalendarError):
        calendar.session(datetime(2027, 1, 1, 10, tzinfo=IST))
    with pytest.raises(CalendarError):
        ExchangeCalendar(tmp_path).year(2026)


def test_calendar_flows_into_weekend_worker_and_candles():
    calendar = ExchangeCalendar(BACKEND_DIR / "app" / "market" / "calendars").year(2026)
    at = datetime(2026, 11, 8, 14, 20, tzinfo=IST)
    worker = TickerWorker(None, 111, 222, calendar=calendar, clock=lambda: at)
    worker._accept(tick(111, at, 100, 100), at)
    worker._accept(
        tick(111, at + timedelta(minutes=1), 110, 110), at + timedelta(minutes=1)
    )
    assert worker.candle_counts[111] == 1
    assert worker.closed_candles[111][0].time == at
    assert worker.status()["session_expected"] is True
    worker._accept(tick(111, at.replace(hour=13), 999, 120), at)
    assert worker.accepted == 2


def test_cross_process_lease_and_bounded_event_resync(tmp_path):
    first, second = ProcessLease(tmp_path / "lease"), ProcessLease(tmp_path / "lease")
    first.acquire()
    first.acquire()
    try:
        with pytest.raises(RuntimeError):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()
    events = MarketEvents()
    events.publish("health", {"stale": False})
    events.publish("health", {"stale": False})
    assert events.sequence == 1
    for number in range(250):
        events.publish("health", {"sample": number})
    snapshot = events.since(0)
    assert len(snapshot["events"]) == 200 and snapshot["resync_required"]
    assert events.since(999)["resync_required"]
    snapshot["events"][0]["kind"] = "tampered"
    assert events.since(0)["events"][0]["kind"] == "health"


@pytest.fixture
def replay_db(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'replay.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_recorded_events_use_production_persistence_and_preserve_provenance(
    replay_db, tmp_path
):
    recorder = TickRecorder(tmp_path / "recordings", 111, 222)
    source = TickerWorker(None, 111, 222, recorder=recorder)
    for minute, price in ((0, 100), (1, 130), (2, 110), (3, 140)):
        for token in source.tokens:
            at = START + timedelta(minutes=minute)
            source._accept(tick(token, at, price, 100 + minute * 10), at)
    source._track_gap("disconnect", START + timedelta(minutes=4), persist=True)
    source.advance_candles(START + timedelta(minutes=5))
    files = sorted(recorder.directory.glob("*.jsonl"))
    calendar = SessionCalendar(
        START.date(),
        START.date(),
        (MarketSession(START, START + timedelta(minutes=375)),),
    )
    store = MarketPersistence(replay_db, "replay-a", 111, 222, box=10, anchor=100)
    result = replay_to_persistence(files, store, calendar)
    assert result["events"] == recorder.sequence
    assert result["candles"] == source.candle_counts
    assert result["bricks"] > 0 and result["entries_enabled"] is False
    with Session(replay_db) as db:
        state = json.loads(db.get(MarketCheckpoint, "replay-a").state)
        assert state["replay"]["sequence"] == recorder.sequence - 1
        assert state["replay"]["files"][0]["sha256"] == result["source"][0]["sha256"]
        assert state["gaps"] and state["gap"]
        assert any(
            json.loads(c.payload)["partial"] for c in db.scalars(select(StoredCandle))
        )
        before = [b.payload for b in db.scalars(select(StoredBrick))]
    with pytest.raises(RuntimeError, match="isolated"):
        replay_to_persistence(files, store, calendar)
    other = MarketPersistence(replay_db, "replay-b", 111, 222, box=10, anchor=100)
    assert replay_to_persistence(files, other, calendar)["bricks"] == result["bricks"]
    with Session(replay_db) as db:
        assert [
            b.payload
            for b in db.scalars(
                select(StoredBrick).where(StoredBrick.stream == "replay-b")
            )
        ] == before


def test_daily_context_exact_previous_and_orb_restart(replay_db, tmp_path):
    # Produce ordinary recorded source bars through the production path.
    recorder = TickRecorder(tmp_path, 111, 222)
    source = TickerWorker(None, 111, 222, recorder=recorder)
    for minute in range(16):
        at = START + timedelta(minutes=minute)
        source._accept(tick(111, at, 100 + minute, 100), at)
    source.advance_candles(START + timedelta(minutes=16))
    calendar = SessionCalendar(
        date(2026, 10, 22),
        START.date(),
        (
            MarketSession(
                START - timedelta(days=1),
                START - timedelta(days=1) + timedelta(minutes=375),
            ),
            MarketSession(START, START + timedelta(minutes=375)),
        ),
    )
    store = MarketPersistence(replay_db, "context-test", 111, 222, box=10, anchor=100)
    replay_to_persistence(sorted(recorder.directory.glob("*.jsonl")), store, calendar)
    context = session_context(
        replay_db, "context-test", 111, calendar, START + timedelta(minutes=16)
    )
    assert (
        context["previous_session"] == "2026-10-22"
        and context["previous_close"] is None
    )
    assert (
        context["opening_range"]["state"] == "partial"
    )  # Sampled first bar cannot claim complete ORB.
    assert context["open"] == "100" and context["high"] == "115"
    restored = LifecycleStore(replay_db).read("context:context-test:2026-10-23")
    assert restored["opening_range"] == context["opening_range"]


def test_migration_up_down_up_isolated_database(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migrate.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")
    engine = database_engine(url)
    try:
        assert "market_lifecycle_state" in inspect(engine).get_table_names()
        command.downgrade(config, "0004_historical_context")
        assert "market_lifecycle_state" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        assert "market_lifecycle_state" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
