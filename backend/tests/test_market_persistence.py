"""Atomic persistence and restart tests use SQLite and synthetic tick data."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.broker.kite_ticker import TickerWorker
from app.db.models import Base, MarketCheckpoint, StoredBrick, StoredCandle
from app.db.session import database_engine
from app.market.persistence import (
    MarketPersistence,
    PersistenceError,
    builder_state,
    encode,
)
from app.market.tick_recording import TickRecorder
from app.tools.replay_ticks import replay_events

START = datetime.fromisoformat("2026-10-23T09:15:00+05:30")


@pytest.fixture
def engine(tmp_path: Path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'market.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def store(engine, *, anchor="24000", stream="NIFTY-test"):
    return MarketPersistence(engine, stream, 111, 222, box="50", anchor=anchor)


def feed(worker, minute, price, token=111, seconds=0):
    ts = START + timedelta(minutes=minute, seconds=seconds)
    worker._accept(
        {
            "instrument_token": token,
            "exchange_timestamp": ts,
            "last_price": price,
            "volume_traded": 100 + minute * 10,
            "oi": 500 + minute,
        },
        ts,
    )


def test_active_candles_counters_and_renko_resume(engine) -> None:
    first_store = store(engine)
    first = TickerWorker(None, 111, 222, persistence=first_store)
    feed(first, 0, 24000)
    feed(first, 0, 24020, token=222)
    feed(first, 1, 24050)
    # First completed candle seeds Renko; no actual brick yet.
    assert first_store.renko.index == 0
    assert first_store.renko.last.index == -1
    assert first_store.renko.last_timestamp == START + timedelta(minutes=1)
    feed(first, 2, 24150)
    feed(first, 5, 24100, token=222)
    before = encode(builder_state(first.candles[222]))
    second_store = store(engine, anchor="24000.0")  # Equivalent grid representation.
    second = TickerWorker(None, 111, 222, persistence=second_store)
    assert second.gap_required is True
    assert second_store.renko.index == 1
    assert second_store.renko.last == first_store.renko.last
    assert second.candles[222].cumulative == first.candles[222].cumulative
    assert second.candles[222].weighted == first.candles[222].weighted
    assert second.candles[222].current.partial is True
    assert json.loads(before)["current"]["close"] == "24100"
    assert second.candle_counts == first.candle_counts
    feed(second, 3, 24200)
    assert second_store.renko.index == 3
    with Session(engine) as db:
        bricks = db.scalars(select(StoredBrick).order_by(StoredBrick.index)).all()
        assert [b.index for b in bricks] == [0, 1, 2]
        assert len(db.scalars(select(StoredCandle)).all()) == 4


def test_checkpoint_with_no_closed_candle_restores_active_seed(engine) -> None:
    first = TickerWorker(None, 111, 222, persistence=store(engine))
    feed(first, 0, "24000.125")
    resumed_store = store(engine)
    resumed = TickerWorker(None, 111, 222, persistence=resumed_store)
    assert resumed.candles[111].current.open == first.candles[111].current.open
    assert resumed_store.renko.last is None
    feed(resumed, 1, "24050.125")
    assert resumed_store.renko.last.index == -1


def test_restart_recording_captures_initial_state_for_offline_replay(
    engine, tmp_path
) -> None:
    first = TickerWorker(None, 111, 222, persistence=store(engine))
    feed(first, 0, 24000)
    feed(first, 0, 24020, token=222)
    feed(first, 1, 24050)
    recorder = TickRecorder(tmp_path, 111, 222)
    resumed = TickerWorker(
        None,
        111,
        222,
        persistence=store(engine),
        recorder=recorder,
        clock=lambda: START + timedelta(minutes=1),
    )
    feed(resumed, 2, 24100)
    resumed.advance_candles(START + timedelta(minutes=5))
    rows = list(replay_events(sorted(recorder.directory.glob("*.jsonl"))))
    assert len(rows) == 3
    assert rows[-1]["candle"]["close"] == 24020
    assert list(replay_events(sorted(recorder.directory.glob("*.jsonl")))) == rows


def test_conflicting_settings_and_concurrent_writers_rejected(engine) -> None:
    original = TickerWorker(None, 111, 222, persistence=store(engine))
    feed(original, 0, 24000)
    with pytest.raises(PersistenceError, match="configuration changed"):
        TickerWorker(None, 111, 222, persistence=store(engine, anchor="24025"))
    stale = TickerWorker(None, 111, 222, persistence=store(engine))
    feed(original, 1, 24050)
    with pytest.raises(PersistenceError):
        feed(stale, 1, 24100)
    with Session(engine) as db:
        assert len(db.scalars(select(StoredCandle)).all()) == 1


def test_failed_save_preserves_committed_checkpoint_and_bricks(engine) -> None:
    persistence = store(engine)
    worker = TickerWorker(None, 111, 222, persistence=persistence)
    feed(worker, 0, 24000)
    feed(worker, 1, 24050)
    revision = persistence.revision
    with patch.object(
        engine.dialect, "do_commit", side_effect=OperationalError("", {}, Exception())
    ):
        with pytest.raises(PersistenceError):
            feed(worker, 2, 24150)
    assert persistence.revision == revision
    assert persistence.renko.index == 0
    restored = TickerWorker(None, 111, 222, persistence=store(engine))
    assert restored.candle_counts[111] == 1
    assert restored.persistence.renko.index == 0


def test_missing_schema_and_corrupt_checkpoint_fail_safely(tmp_path, engine) -> None:
    missing = database_engine(f"sqlite:///{(tmp_path / 'missing.db').as_posix()}")
    try:
        with pytest.raises(PersistenceError, match="alembic"):
            TickerWorker(None, 111, 222, persistence=store(missing))
    finally:
        missing.dispose()
    worker = TickerWorker(None, 111, 222, persistence=store(engine))
    feed(worker, 0, 24000)
    with Session(engine) as db, db.begin():
        db.get(MarketCheckpoint, "NIFTY-test").state = "{}"
    with pytest.raises(PersistenceError, match="checkpoint is invalid"):
        TickerWorker(None, 111, 222, persistence=store(engine))
