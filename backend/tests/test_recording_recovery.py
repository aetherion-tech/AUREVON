"""Crash reconciliation uses synthetic data, isolated SQLite and frozen files."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_market_persistence import START, feed, store

from app.broker.kite_ticker import TickerWorker
from app.db.models import Base, MarketCheckpoint, StoredBrick, StoredCandle
from app.db.session import database_engine
from app.market.persistence import PersistenceError
from app.market.tick_recording import TickRecorder


@pytest.fixture
def engine(tmp_path):
    database = database_engine(f"sqlite:///{(tmp_path / 'market.db').as_posix()}")
    Base.metadata.create_all(database)
    yield database
    database.dispose()


def worker_for(engine, root):
    return TickerWorker(
        None,
        111,
        222,
        persistence=store(engine),
        recorder=TickRecorder(root, 111, 222),
        clock=lambda: START,
    )


def db_state(engine):
    with Session(engine) as db:
        return (
            db.get(MarketCheckpoint, "NIFTY-test").state,
            [
                x.payload
                for x in db.scalars(
                    select(StoredCandle).order_by(StoredCandle.token, StoredCandle.time)
                )
            ],
            [
                x.payload
                for x in db.scalars(select(StoredBrick).order_by(StoredBrick.index))
            ],
        )


@pytest.mark.parametrize("kind", ["spot", "future", "advance", "gap"])
def test_failed_transaction_tail_replayed_once(engine, tmp_path, kind):
    original = worker_for(engine, tmp_path)
    feed(original, 0, 24000)
    feed(original, 0, 24000, token=222)
    feed(original, 1, 24050)
    previous = db_state(engine)
    with patch.object(
        engine.dialect, "do_commit", side_effect=OperationalError("", {}, Exception())
    ):
        with pytest.raises(PersistenceError):
            if kind == "spot":
                feed(original, 2, 24150)
            elif kind == "future":
                feed(original, 5, 24150, token=222)
            elif kind == "advance":
                original.advance_candles(START + timedelta(minutes=5))
            else:
                original._track_gap("disconnect", START + timedelta(minutes=2))
    assert db_state(engine) == previous
    files = sorted(original.recorder.directory.glob("*.jsonl"))
    recorded = [p.read_bytes() for p in files]
    expected_counts = original.candle_counts.copy()
    resumed = worker_for(engine, tmp_path)
    assert resumed.candle_counts == expected_counts
    assert len(db_state(engine)[1]) == sum(expected_counts.values())
    expected = db_state(engine)[1:]
    assert [p.read_bytes() for p in files] == recorded
    again = worker_for(engine, tmp_path)
    assert db_state(engine)[1:] == expected
    assert again.candle_counts == resumed.candle_counts


def test_tail_replay_after_crash_and_repeated_restart(engine, tmp_path):
    original = worker_for(engine, tmp_path)
    feed(original, 0, 24000)
    with patch.object(
        engine.dialect, "do_commit", side_effect=OperationalError("", {}, Exception())
    ):
        with pytest.raises(PersistenceError):
            feed(original, 1, 24100)
    assert original.candle_counts[111] == 1
    resumed = worker_for(engine, tmp_path)
    assert resumed.candle_counts[111] == 1
    assert resumed.candles[111].current.close == 24100
    assert len(db_state(engine)[1]) == 1
    worker_for(engine, tmp_path)
    assert len(db_state(engine)[1]) == 1


@pytest.mark.parametrize(
    "damage", ["truncated", "missing", "sequence", "tokens", "config"]
)
def test_invalid_recording_stops_before_db_writes(engine, tmp_path, damage):
    original = worker_for(engine, tmp_path)
    feed(original, 0, 24000)
    path = next(original.recorder.directory.glob("*.jsonl"))
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    if damage == "missing":
        path.unlink()
    elif damage == "truncated":
        path.write_text(path.read_text() + "{")
    else:
        if damage == "sequence":
            rows[1]["sequence"] = 100
        elif damage == "tokens":
            rows[0]["spot_token"] = 999
        else:
            rows[0]["configuration"] = "changed"
        path.write_text("".join(json.dumps(x) + "\n" for x in rows))
    before = db_state(engine)
    with pytest.raises(PersistenceError, match="Recording"):
        worker_for(engine, tmp_path)
    assert db_state(engine) == before


def test_missing_recorder_cannot_skip_reconciliation(engine, tmp_path):
    worker_for(engine, tmp_path)
    with pytest.raises(PersistenceError, match="retained recording"):
        TickerWorker(None, 111, 222, persistence=store(engine))


def test_crash_during_reconciliation_resumes_committed_cursor(engine, tmp_path):
    from app.market.persistence import MarketPersistence

    original = worker_for(engine, tmp_path)
    feed(original, 0, 24000)
    original_store = original.persistence
    original.persistence = None
    for minute in range(1, 4):
        feed(original, minute, 24000 + minute * 100)
    original.persistence = original_store
    save = MarketPersistence.save
    calls = 0

    def interrupted(self, worker):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise PersistenceError("crash during replay")
        return save(self, worker)

    with patch.object(MarketPersistence, "save", interrupted):
        with pytest.raises(PersistenceError, match="crash during replay"):
            worker_for(engine, tmp_path)
    with Session(engine) as db:
        cursor = json.loads(db.get(MarketCheckpoint, "NIFTY-test").state)[
            "recording_cursor"
        ]
        assert cursor["sequence"] == 2
    resumed = worker_for(engine, tmp_path)
    assert resumed.candle_counts[111] == 3
    expected = db_state(engine)[1:]
    worker_for(engine, tmp_path)
    assert db_state(engine)[1:] == expected


def test_tail_across_daily_files_and_same_timestamp_updates(engine, tmp_path):
    original = worker_for(engine, tmp_path)
    feed(original, 0, 24000, token=222)
    original_store = original.persistence
    original.persistence = None
    feed(original, 0, 24050, token=222)
    feed(original, 0, 24100, token=222)
    feed(original, 4320, 24200, token=222)
    original.persistence = original_store
    assert len(list(original.recorder.directory.glob("*.jsonl"))) == 2
    resumed = worker_for(engine, tmp_path)
    assert resumed.candles[222].cumulative == original.candles[222].cumulative
    assert resumed.candle_counts == original.candle_counts
    assert resumed.candles[222].current.close == 24200
