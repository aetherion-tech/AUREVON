"""Bounded tick queue; SDK callbacks never calculate indicators or place orders."""

import asyncio
import math
from collections import deque
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, time
from threading import BoundedSemaphore
from typing import Any

from app.broker.kite_auth import IST
from app.market.candles_5m import CandleBuilder, MarketCandle
from app.market.persistence import MarketPersistence
from app.market.tick_recording import TickRecorder


class TickerWorker:
    def __init__(
        self,
        socket: Any,
        spot_token: int,
        future_token: int,
        *,
        capacity: int = 4096,
        clock: Callable[[], datetime] | None = None,
        recorder: TickRecorder | None = None,
        persistence: MarketPersistence | None = None,
    ) -> None:
        if spot_token <= 0 or future_token <= 0 or spot_token == future_token:
            raise ValueError("Supply distinct positive spot and futures tokens")
        if capacity <= 0:
            raise ValueError("Queue capacity must be positive")
        self.socket = socket
        self.recorder = recorder
        self.persistence = persistence
        self.tokens = [spot_token, future_token]
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(capacity)
        self._pending = BoundedSemaphore(capacity)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.loop: asyncio.AbstractEventLoop | None = None
        self.connected = False
        self.running = False
        self.exhausted = False
        self.gap_required = False
        self.dropped = 0
        self.invalid = 0
        self.accepted = 0
        self.reconnects = 0
        self.latest: dict[int, dict[str, Any]] = {}
        self.received: dict[int, datetime] = {}
        self.task: asyncio.Task[None] | None = None
        self.candles = {
            spot_token: CandleBuilder(1, futures=False),
            future_token: CandleBuilder(5, futures=True),
        }
        self.closed_candles: dict[int, deque[MarketCandle]] = {
            token: deque(maxlen=100) for token in self.tokens
        }
        self.candle_counts = dict.fromkeys(self.tokens, 0)
        if persistence is not None and persistence.restore(self):
            self._disconnected()
            if self.recorder is not None:
                self.recorder.write(
                    "checkpoint",
                    self.clock(),
                    {
                        "checkpoint": persistence.snapshot(self),
                    },
                )

    async def start(self) -> None:
        if self.running:
            raise ValueError("Ticker already running")
        self.loop = asyncio.get_running_loop()
        self.running = True
        self.socket.on_ticks = self._on_ticks
        self.socket.on_connect = self._on_connect
        self.socket.on_close = self._on_close
        self.socket.on_error = self._on_close
        self.socket.on_noreconnect = self._on_exhausted
        self.task = asyncio.create_task(self._consume())
        try:
            self.socket.connect(threaded=True)
        except Exception:
            await self.stop()
            raise RuntimeError("Could not start Kite price feed") from None

    def _schedule(self, callback: Callable[..., None], *args: Any) -> None:
        if self.running and self.loop is not None and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(callback, *args)

    def _on_ticks(self, socket: Any, ticks: list[dict[str, Any]]) -> None:
        if not self.running:
            return
        received = self.clock()
        for tick in ticks:
            if self._pending.acquire(blocking=False):
                self._schedule(self._deliver, dict(tick), received)
            else:
                self.dropped += 1
                self.gap_required = True

    def _deliver(self, tick: dict[str, Any], received: datetime) -> None:
        try:
            self._enqueue([tick], received)
        finally:
            self._pending.release()

    def _enqueue(self, ticks: list[dict[str, Any]], received: datetime) -> None:
        if not self.running:
            return
        for tick in ticks:
            try:
                self.queue.put_nowait({"tick": dict(tick), "received": received})
            except asyncio.QueueFull:
                self.dropped += 1
                self.gap_required = True
                for builder in self.candles.values():
                    builder.mark_gap()

    def _on_connect(self, socket: Any, response: Any) -> None:
        # Always resubscribe, including after SDK reconnects.
        socket.subscribe(self.tokens)
        socket.set_mode(socket.MODE_FULL, self.tokens)
        self._schedule(self._connected)

    def _connected(self) -> None:
        self.connected = True
        self.reconnects += 1

    def _on_close(self, socket: Any, *args: Any) -> None:
        self._schedule(self._disconnected)

    def _disconnected(self) -> None:
        self.connected = False
        self.gap_required = True
        for builder in self.candles.values():
            builder.mark_gap()

    def _on_exhausted(self, socket: Any) -> None:
        self._schedule(self._mark_exhausted)

    def _mark_exhausted(self) -> None:
        self.exhausted = True
        self._disconnected()

    async def _consume(self) -> None:
        while True:
            item = await self.queue.get()
            try:
                self._accept(item["tick"], item["received"])
            finally:
                self.queue.task_done()

    def _accept(self, tick: dict[str, Any], received: datetime) -> None:
        try:
            token = tick["instrument_token"]
            price = float(tick["last_price"])
            ts = tick["exchange_timestamp"]
            if token not in self.tokens or not math.isfinite(price) or price <= 0:
                raise ValueError
            if not isinstance(ts, datetime):
                raise ValueError
            # SDK decodes exchange epoch with datetime.fromtimestamp(), producing
            # naive system-local time. astimezone() applies that system timezone.
            ts = ts.astimezone(UTC)
            if token in self.latest and ts < self.latest[token]["time"]:
                raise ValueError
            if self.gap_required:
                for builder in self.candles.values():
                    builder.mark_gap()
            closed = self.candles[token].on_tick(
                tick["last_price"],
                ts,
                cumulative_volume=tick.get("volume_traded"),
                oi=tick.get("oi"),
            )
            self._store_candles(token, closed)
            # Distinct updates in the same exchange second are legitimate.
            self.latest[token] = {
                "time": ts,
                "price": price,
                "volume": tick.get("volume_traded"),
                "oi": tick.get("oi"),
            }
            self.received[token] = received
            self.accepted += 1
            if self.recorder is not None:
                self.recorder.write(
                    "tick",
                    received,
                    {
                        "token": token,
                        "price": str(tick["last_price"]),
                        "exchange_time": ts.isoformat(),
                        "volume": str(tick["volume_traded"])
                        if tick.get("volume_traded") is not None
                        else None,
                        "oi": str(tick["oi"]) if tick.get("oi") is not None else None,
                        "gap": self.gap_required,
                    },
                )
            if self.persistence is not None:
                self.persistence.save(self)
        except (KeyError, TypeError, ValueError, OverflowError):
            self.invalid += 1

    def _store_candles(self, token: int, candles: list[MarketCandle]) -> None:
        self.closed_candles[token].extend(candles)
        self.candle_counts[token] += len(candles)

    def advance_candles(self, now: datetime | None = None) -> None:
        """Call after queued ticks drain, including at the end of the session."""
        at = now or self.clock()
        if self.recorder is not None:
            self.recorder.write("advance", at, {"gap": self.gap_required})
        for token, builder in self.candles.items():
            if self.gap_required:
                builder.mark_gap()
            self._store_candles(token, builder.advance(at))
        if self.persistence is not None:
            self.persistence.save(self)

    def status(self) -> dict[str, Any]:
        now = self.clock()
        local = now.astimezone(IST)
        session = local.weekday() < 5 and time(9, 15) <= local.time() < time(15, 30)
        stale = session and any(
            token not in self.received
            or (now - self.received[token]).total_seconds() > 5
            or (now - self.latest[token]["time"]).total_seconds() > 5
            for token in self.tokens
        )
        drift = any(
            abs((now - tick["time"]).total_seconds()) > 2
            for tick in self.latest.values()
        )
        return {
            "connected": self.connected,
            "stale": stale,
            "session_expected": session,
            "clock_or_feed_delay": drift,
            "gap_requires_replay": self.gap_required,
            "reconnect_exhausted": self.exhausted,
            "accepted": self.accepted,
            "invalid": self.invalid,
            "dropped": self.dropped,
            "queued": self.queue.qsize(),
            "connections": self.reconnects,
            "entries_enabled": False,
            "persisted_stream": self.persistence.stream
            if self.persistence is not None
            else None,
            "renko_bricks": self.persistence.renko.index
            if self.persistence is not None
            else None,
            "last_renko_brick": asdict(self.persistence.renko.last)
            if self.persistence is not None and self.persistence.renko.last is not None
            else None,
            "latest": self.latest,
            "closed_candle_counts": self.candle_counts,
            "last_closed_candles": {
                token: asdict(candles[-1]) if candles else None
                for token, candles in self.closed_candles.items()
            },
            "recording_directory": str(self.recorder.directory)
            if self.recorder is not None
            else None,
        }

    async def stop(self) -> None:
        self.running = False
        self.connected = False
        try:
            if self.task is not None:
                if not self.task.done():
                    drain = asyncio.create_task(self.queue.join())
                    try:
                        await asyncio.wait(
                            [drain, self.task], return_when=asyncio.FIRST_COMPLETED
                        )
                    finally:
                        drain.cancel()
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
        finally:
            # SDK socket operations run on its Twisted reactor thread.
            from twisted.internet import reactor

            reactor.callFromThread(self.socket.close)
            reactor.callFromThread(self.socket.stop_retry)
