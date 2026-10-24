"""Socket callbacks and clock are fake; no network connection is opened."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from app.broker.kite_ticker import TickerWorker

NOW = datetime.fromisoformat("2026-10-23T10:00:00+05:30")


def tick(token: int = 111, ts: datetime = NOW, price: float = 24000) -> dict:
    return {
        "instrument_token": token,
        "exchange_timestamp": ts,
        "last_price": price,
        "volume_traded": 10,
        "oi": 20,
    }


@pytest.mark.asyncio
async def test_subscription_queue_reconnect_and_shutdown() -> None:
    socket = Mock()
    worker = TickerWorker(socket, 111, 222, clock=lambda: NOW)
    with patch("twisted.internet.reactor.callFromThread") as call:
        await worker.start()
        socket.connect.assert_called_once_with(threaded=True)
        socket.on_connect(socket, {})
        socket.on_ticks(socket, [tick(), tick(222)])
        await asyncio.sleep(0)
        await worker.queue.join()
        assert worker.status()["accepted"] == 2
        assert worker.status()["stale"] is False
        socket.subscribe.assert_called_with([111, 222])
        socket.set_mode.assert_called_with(socket.MODE_FULL, [111, 222])
        socket.on_close(socket, 1006, "private-url-with-token")
        await asyncio.sleep(0)
        assert worker.status()["gap_requires_replay"] is True
        assert worker.status()["connected"] is False
        socket.on_connect(socket, {})
        await asyncio.sleep(0)
        assert worker.status()["connections"] == 2
        assert socket.subscribe.call_count == 2
        assert worker.status()["entries_enabled"] is False
        await worker.stop()
        assert call.call_count == 2
        assert worker.task.done()


def test_stale_per_token_delayed_prices_invalid_and_same_second_updates() -> None:
    worker = TickerWorker(Mock(), 111, 222, clock=lambda: NOW)
    worker._accept(tick(), NOW)
    assert worker.status()["stale"] is True  # Futures still missing.
    worker._accept(tick(222), NOW)
    assert worker.status()["stale"] is False
    worker._accept(tick(price=24001), NOW)
    assert worker.accepted == 3
    worker._accept(tick(ts=NOW - timedelta(seconds=1)), NOW)
    worker._accept(tick(price=float("nan")), NOW)
    worker._accept(tick(333), NOW)
    assert worker.invalid == 3
    worker.clock = lambda: NOW + timedelta(seconds=6)
    assert worker.status()["stale"] is True
    assert worker.status()["clock_or_feed_delay"] is True
    worker.clock = lambda: NOW + timedelta(days=1)  # Saturday.
    assert worker.status()["session_expected"] is False
    assert worker.status()["stale"] is False


def test_overflow_requires_replay() -> None:
    worker = TickerWorker(Mock(), 111, 222, capacity=1)
    worker.running = True
    worker._enqueue([tick(), tick(222)], NOW)
    assert worker.queue.qsize() == 1
    assert worker.dropped == 1
    assert worker.gap_required is True


def test_naive_sdk_timestamp_uses_system_timezone() -> None:
    worker = TickerWorker(Mock(), 111, 222)
    naive = datetime.now()
    worker._accept(tick(ts=naive), NOW)
    assert worker.latest[111]["time"] == naive.astimezone(UTC)


def test_worker_publishes_only_closed_candles_and_marks_disconnect() -> None:
    worker = TickerWorker(Mock(), 111, 222, clock=lambda: NOW)
    worker._accept(tick(), NOW)
    worker._accept(tick(222), NOW)
    assert worker.status()["last_closed_candles"] == {111: None, 222: None}
    later = NOW + timedelta(minutes=1)
    worker._accept(tick(ts=later, price=24050), later)
    status = worker.status()
    assert status["closed_candle_counts"] == {111: 1, 222: 0}
    assert status["last_closed_candles"][111]["close"] == 24000
    worker._disconnected()
    worker.advance_candles(NOW + timedelta(minutes=5))
    status = worker.status()
    assert status["closed_candle_counts"] == {111: 2, 222: 1}
    assert status["last_closed_candles"][222]["partial"] is True
    assert status["last_closed_candles"][222]["vwap"] is None


@pytest.mark.asyncio
async def test_exhaustion_and_start_failure() -> None:
    socket = Mock()
    worker = TickerWorker(socket, 111, 222)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start()
        socket.on_noreconnect(socket)
        await asyncio.sleep(0)
        assert worker.exhausted is True
        await worker.stop()
        socket.connect.side_effect = RuntimeError("private")
        with pytest.raises(RuntimeError, match="Could not start"):
            await worker.start()
        assert worker.running is False


@pytest.mark.parametrize("spot,future", [(0, 2), (1, 1), (1, -2)])
def test_invalid_tokens(spot: int, future: int) -> None:
    with pytest.raises(ValueError):
        TickerWorker(Mock(), spot, future)
