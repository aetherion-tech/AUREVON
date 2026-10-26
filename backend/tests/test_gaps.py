"""Synthetic gap incidents; no broker, guessed holiday calendar or live orders."""

import json
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from app.broker.kite_ticker import TickerWorker
from app.db.models import Base
from app.db.session import database_engine
from app.market.gaps import GapTracker
from app.market.persistence import MarketPersistence
from app.market.tick_recording import TickRecorder
from app.market.warmup import Session, SessionCalendar
from app.tools.replay_ticks import replay_events

NOW = datetime.fromisoformat("2026-10-23T10:02:00+05:30")


def tick(token=111, at=NOW):
    return {
        "instrument_token": token,
        "exchange_timestamp": at,
        "last_price": 24000,
        "volume_traded": 100,
        "oi": 10,
    }


def calendar():
    return SessionCalendar(
        date(2026, 10, 23),
        date(2026, 10, 26),
        (
            Session(NOW.replace(hour=9, minute=15), NOW.replace(hour=15, minute=30)),
            Session(
                NOW.replace(day=26, hour=9, minute=15),
                NOW.replace(day=26, hour=15, minute=30),
            ),
        ),
    )


def test_disconnect_reconnect_tracks_each_token_until_actual_resume():
    worker = TickerWorker(Mock(), 111, 222, clock=lambda: NOW)
    worker._accept(tick(), NOW)
    worker._accept(tick(222), NOW)
    worker._connected()
    worker.clock = lambda: NOW + timedelta(minutes=2)
    worker._disconnected()
    worker._connected()
    assert len(worker.gaps.snapshot()) == 4
    # Queued ticks predating the loss cannot close an open uncertainty span.
    worker._accept(tick(at=NOW + timedelta(seconds=1)), NOW)
    assert all(g["end"] is None for g in worker.gaps.snapshot())
    resume = NOW + timedelta(minutes=3)
    worker._accept(tick(at=resume), resume)
    assert all(g["end"] == resume for g in worker.gaps.snapshot() if g["token"] == 111)
    assert all(g["end"] is None for g in worker.gaps.snapshot() if g["token"] == 222)
    assert worker.gap_required is True


def test_sdk_overflow_retains_delayed_exchange_bucket():
    worker = TickerWorker(
        Mock(), 111, 222, capacity=1, clock=lambda: NOW + timedelta(minutes=10)
    )
    worker.running = True
    assert worker._pending.acquire(blocking=False)
    worker._on_ticks(None, [tick()])
    worker._pending.release()
    assert all(g["start"] == NOW for g in worker.gaps.snapshot())
    assert all(
        g["resume_after"] == NOW + timedelta(minutes=10) for g in worker.gaps.snapshot()
    )
    assert worker.status()["entries_enabled"] is False


def test_overflow_queue_and_sdk_pending_callbacks_are_bounded():
    worker = TickerWorker(Mock(), 111, 222, capacity=1, clock=lambda: NOW)
    worker.running = True
    worker._enqueue([tick(), tick()], NOW)
    assert {g["reason"] for g in worker.gaps.snapshot()} == {"overflow"}
    assert worker._pending.acquire(blocking=False)
    for _ in range(100):
        worker._on_ticks(None, [tick()])
    worker._pending.release()
    assert len(worker.gaps.snapshot()) == 2
    assert worker.dropped == 101
    assert worker.queue.qsize() == 1
    assert worker.gap_required is True


def test_completed_recovery_buckets_clip_to_explicit_sessions_and_exclude_holidays():
    tracker = GapTracker([111])
    tracker.mark(111, "disconnect", NOW.replace(hour=15, minute=29))
    finish = NOW.replace(day=26, hour=9, minute=22)
    tracker.resume(111, finish)
    ranges = tracker.ranges(111, 5, calendar(), finish)
    assert [(r.start.isoformat(), r.end.isoformat()) for r in ranges] == [
        ("2026-10-23T15:25:00+05:30", "2026-10-23T15:25:00+05:30"),
        ("2026-10-26T09:15:00+05:30", "2026-10-26T09:15:00+05:30"),
    ]
    assert all(r.completed_through <= finish for r in ranges)


def test_open_gaps_merge_reasons_and_wait_for_unfinished_candles():
    tracker = GapTracker([111])
    tracker.mark(111, "overflow", NOW)
    tracker.mark(111, "disconnect", NOW + timedelta(minutes=1))
    assert tracker.ranges(111, 5, calendar(), NOW) == ()
    ranges = tracker.ranges(111, 1, calendar(), NOW + timedelta(minutes=4, seconds=30))
    assert len(ranges) == 1
    assert ranges[0].start == NOW
    assert ranges[0].end == NOW + timedelta(minutes=3)
    with pytest.raises(ValueError, match="cover"):
        tracker.ranges(111, 1, calendar(), NOW + timedelta(days=5))


def test_envelopes_keep_earliest_loss_and_latest_resume_without_unbounded_growth():
    tracker = GapTracker([111])
    for i in range(100):
        at = NOW + timedelta(seconds=i)
        tracker.mark(111, "overflow", at)
        tracker.resume(111, at + timedelta(seconds=1))
    restored = GapTracker([111])
    restored.restore(json.loads(json.dumps(tracker.snapshot(), default=str)))
    assert restored.snapshot() == tracker.snapshot()
    assert len(restored.snapshot()) == 1
    assert restored.snapshot()[0]["start"] == NOW
    assert restored.snapshot()[0]["end"] == NOW + timedelta(seconds=100)


def test_merging_seed_keeps_callback_tracker_identity_and_unresolved_incidents():
    live, seed = GapTracker([111]), GapTracker([111])
    live.mark(111, "overflow", NOW + timedelta(minutes=2))
    seed.mark(111, "overflow", NOW)
    seed.resume(111, NOW + timedelta(minutes=1))
    seed.mark(111, "downtime", NOW)
    live.absorb(seed)
    overflow = next(g for g in live.snapshot() if g["reason"] == "overflow")
    assert overflow["start"] == NOW
    assert overflow["resume_after"] == NOW + timedelta(minutes=2)
    assert overflow["end"] is None
    assert len(live.snapshot()) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"token": 999},
        {"reason": "private socket error"},
        {"start": "2026-10-23T10:00:00"},
        {"end": "2026-10-22T10:00:00+05:30"},
    ],
)
def test_invalid_gap_checkpoints_are_rejected(change):
    tracker = GapTracker([111])
    tracker.mark(111, "downtime", NOW)
    row = tracker.snapshot()[0] | change
    with pytest.raises(ValueError):
        tracker.restore([row])


def test_restart_persists_gap_without_waiting_for_another_tick(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'gap.db').as_posix()}")
    Base.metadata.create_all(engine)

    def store():
        return MarketPersistence(engine, "test", 111, 222, box=50, anchor=24000)

    worker = TickerWorker(None, 111, 222, persistence=store(), clock=lambda: NOW)
    worker._accept(tick(), NOW)
    worker.clock = lambda: NOW + timedelta(minutes=1)
    worker._disconnected()
    restored = TickerWorker(
        None, 111, 222, persistence=store(), clock=lambda: NOW + timedelta(minutes=5)
    )
    spans = restored.gaps.snapshot()
    assert {g["reason"] for g in spans} == {"disconnect", "downtime"}
    assert next(g for g in spans if g["token"] == 111)["start"] == NOW
    assert restored.gap_required is True
    assert restored.status()["entries_enabled"] is False
    engine.dispose()


def test_gap_recording_preserves_event_order_and_replays_partial_candles(tmp_path):
    recorder = TickRecorder(tmp_path, 111, 222)
    worker = TickerWorker(None, 111, 222, recorder=recorder, clock=lambda: NOW)
    worker._accept(tick(), NOW)
    worker._disconnected()
    worker.advance_candles(NOW + timedelta(minutes=1))
    rows = list(replay_events(sorted(recorder.directory.glob("*.jsonl"))))
    assert len(rows) == 1
    assert rows[0]["candle"]["partial"] is True


@pytest.mark.asyncio
async def test_history_buffering_does_not_write_gap_ahead_of_seed_checkpoint(tmp_path):
    recorder = TickRecorder(tmp_path, 111, 222)
    worker = TickerWorker(Mock(), 111, 222, recorder=recorder, clock=lambda: NOW)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        worker._disconnected()
        assert recorder.sequence == 0
        assert len(worker.gaps.snapshot()) == 2
        await worker.stop()
