"""Bounded tick queue; SDK callbacks never calculate indicators or place orders."""

import asyncio
import math
from collections import deque
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, time
from threading import BoundedSemaphore
from time import monotonic
from typing import Any

from app.broker.kite_auth import IST
from app.config import Settings
from app.market.candles_5m import CandleBuilder, MarketCandle
from app.market.five_minute_renko import FiveMinuteCloseRenko
from app.market.gaps import GapReason, GapTracker
from app.market.persistence import MarketPersistence, PersistenceError
from app.market.readiness import ResumeGate, validate_history
from app.market.recovery_progress import RecoveryProgress
from app.market.tick_recording import TickRecorder
from app.market.warmup import SessionCalendar
from app.strategy.models import OptionContract
from app.strategy.quotes import OptionQuoteBook


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
        elapsed_clock: Callable[[], float] = monotonic,
        recovery_progress: RecoveryProgress | None = None,
        calendar: SessionCalendar | None = None,
    ) -> None:
        if spot_token <= 0 or future_token <= 0 or spot_token == future_token:
            raise ValueError("Supply distinct positive spot and futures tokens")
        if capacity <= 0:
            raise ValueError("Queue capacity must be positive")
        self.recovery_progress = (
            recovery_progress if recovery_progress is not None else RecoveryProgress()
        )
        self.resume_gate = ResumeGate(60, elapsed_clock)
        self.calendar = calendar
        self.socket = socket
        self.recorder = recorder
        self.persistence = persistence
        self.recording_cursor: dict[str, Any] | None = None
        self.tokens = [spot_token, future_token]
        self.option_quotes = OptionQuoteBook()
        self._option_lock = asyncio.Lock()
        self.gaps = GapTracker(self.tokens)
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
        self._history_ready = asyncio.Event()
        self._history_ready.set()
        self.history_overlap = 0
        self.candles = {
            spot_token: CandleBuilder(1, futures=False, calendar=calendar),
            future_token: CandleBuilder(5, futures=True, calendar=calendar),
        }
        self.closed_candles: dict[int, deque[MarketCandle]] = {
            token: deque(maxlen=100) for token in self.tokens
        }
        self.candle_counts = dict.fromkeys(self.tokens, 0)
        restored = persistence is not None and persistence.restore(self)
        if restored:
            if self.recording_cursor is not None:
                from app.market.recording_recovery import reconcile_recording

                reconcile_recording(self)
            self.recovery_progress.restore_sources(
                {
                    t: self.closed_candles[t][-1].end
                    for t in self.tokens
                    if self.closed_candles[t]
                }
            )
            self._track_gap("downtime", self.clock(), persist=False)
        if persistence is not None and self.recorder is not None:
            self._record(
                "checkpoint",
                self.clock(),
                {
                    "checkpoint": persistence.snapshot(self),
                    "configuration": persistence.configuration,
                },
            )
            persistence.save(self)

    def _record(self, kind: str, at: datetime, payload: dict[str, Any]) -> None:
        if self.recorder is not None:
            self.recorder.write(kind, at, payload)
            self.recording_cursor = {
                "session": self.recorder.directory.name,
                "sequence": self.recorder.sequence - 1,
            }

    async def start(self, *, buffer_only: bool = False) -> None:
        if self.running:
            raise ValueError("Ticker already running")
        self.loop = asyncio.get_running_loop()
        self.running = True
        if buffer_only:
            if self.accepted or self.persistence is not None:
                self.running = False
                raise ValueError("Historical buffering requires a fresh worker")
            self._history_ready.clear()
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
                # Only bounded, locked metadata is changed on the SDK thread.
                start = received
                stamp = tick.get("exchange_timestamp")
                if isinstance(stamp, datetime):
                    try:
                        start = min(received, stamp.astimezone(UTC))
                    except (ValueError, OverflowError, OSError):
                        pass
                for token in self.tokens:
                    self.gaps.mark(token, "overflow", start, resume_after=received)

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
                self._track_gap("overflow", received)

    def _on_connect(self, socket: Any, response: Any) -> None:
        # Always resubscribe, including after SDK reconnects.
        tokens = self.tokens + self.option_quotes.tokens
        socket.subscribe(tokens)
        socket.set_mode(socket.MODE_FULL, tokens)
        self._schedule(self._connected)

    async def set_option_contracts(
        self,
        candidates: list[OptionContract],
        traded: list[OptionContract] | None = None,
    ) -> None:
        async with self._option_lock:
            await self._set_option_contracts(candidates, traded)

    async def _set_option_contracts(
        self,
        candidates: list[OptionContract],
        traded: list[OptionContract] | None = None,
    ) -> None:
        """Call on the worker loop. Traded contracts stay pinned during previews."""
        if set(self.tokens) & {c.token for c in candidates + (traded or [])}:
            raise ValueError("option token collides with core market identity")
        old = set(self.option_quotes.tokens)
        self.option_quotes.configure(candidates, traded)
        desired = set(self.option_quotes.tokens)
        retry = self.option_quotes.subscription_error
        if not self.running or not self.connected or (old == desired and not retry):
            return
        from twisted.internet import reactor

        loop = asyncio.get_running_loop()
        complete: asyncio.Future[None] = loop.create_future()

        def apply() -> None:
            try:
                removed = sorted(old - desired)
                added = sorted(desired if retry else desired - old)
                if removed:
                    self.socket.unsubscribe(removed)
                if added:
                    self.socket.subscribe(added)
                    self.socket.set_mode(self.socket.MODE_FULL, added)
                loop.call_soon_threadsafe(finish, None)
            except Exception:
                self.option_quotes.subscription_error = True
                self.option_quotes.invalidate()
                loop.call_soon_threadsafe(
                    finish, RuntimeError("option subscription failed")
                )

        def finish(error: Exception | None) -> None:
            if complete.done():
                return
            if error:
                complete.set_exception(error)
            else:
                self.option_quotes.subscription_error = False
                complete.set_result(None)

        reactor.callFromThread(apply)
        try:
            await asyncio.wait_for(complete, timeout=2)
        except BaseException:
            self.option_quotes.subscription_error = True
            self.option_quotes.invalidate()
            raise

    def _connected(self) -> None:
        self.option_quotes.invalidate()
        self.option_quotes.subscription_error = False
        if self.reconnects:
            self._track_gap("reconnect", self.clock())
        self.connected = True
        self.reconnects += 1

    def _on_close(self, socket: Any, *args: Any) -> None:
        self._schedule(self._disconnected)

    def _disconnected(self) -> None:
        self.option_quotes.invalidate()
        self.connected = False
        self._track_gap("disconnect", self.clock())

    def _track_gap(
        self, reason: GapReason, at: datetime, *, persist: bool = True
    ) -> None:
        self.option_quotes.invalidate()
        self.resume_gate.revoke()
        self.recovery_progress.invalidate()
        self.gap_required = True
        for token, builder in self.candles.items():
            start = (
                builder.current.time
                if builder.current is not None
                else builder._closed_until or builder.last_time or at
            )
            self.gaps.mark(token, reason, min(start, at), resume_after=at)
            builder.mark_gap()
        if persist and self._history_ready.is_set():
            if self.recorder is not None:
                self._record(
                    "gap",
                    at,
                    {
                        "gap": True,
                        "gaps": self.gaps.snapshot(),
                    },
                )
            if self.persistence is not None:
                self.persistence.save(self)

    def _on_exhausted(self, socket: Any) -> None:
        self._schedule(self._mark_exhausted)

    def _mark_exhausted(self) -> None:
        self.exhausted = True
        self._disconnected()

    async def _consume(self) -> None:
        while True:
            await self._history_ready.wait()
            item = await self.queue.get()
            try:
                self._accept(item["tick"], item["received"])
            finally:
                self.queue.task_done()

    def merge_history(
        self,
        persistence: MarketPersistence,
        boundaries: dict[int, datetime],
        *,
        _validated_revision: int | None = None,
    ) -> None:
        """Adopt history while callbacks keep buffering, then drain in queue order.

        Each boundary is an exclusive history end / inclusive live start for that
        instrument. Use the beginning of the unfinished minute/five-minute bucket,
        not the wall clock download completion time. Missing history stays gapped.
        Call on the worker event loop; no consumer or clock may run during adoption.
        """
        if (
            not self.running
            or self._history_ready.is_set()
            or self.accepted
            or self.persistence is not None
            or (self.recorder is not None and self.recorder.sequence != 0)
        ):
            raise ValueError("Historical merge requires an untouched buffering worker")
        if set(boundaries) != set(self.tokens):
            raise ValueError("Supply an explicit boundary for each instrument")
        if _validated_revision is None:
            restored = TickerWorker(
                None, *self.tokens, persistence=persistence, calendar=self.calendar
            )
        else:
            restored = TickerWorker(None, *self.tokens, calendar=self.calendar)
            if (
                not persistence.restore(restored)
                or persistence.revision != _validated_revision
            ):
                raise PersistenceError("Checkpoint changed after validation")
            if self.gaps.snapshot() or self.gap_required:
                raise PersistenceError("A new feed gap requires recovery")
            persistence.metadata["validated_recovery"] = {
                "source_revision": _validated_revision,
                "retired_gaps": restored.gaps.snapshot(),
                "completed_through": boundaries,
                "unfinished_live_bucket_partial": True,
            }
            restored.gaps.restore([])
            restored.gap_required = False
            for builder in restored.candles.values():
                # All completed source flags and VWAP totals were independently proved.
                builder.vwap_partial = False
                builder._next_partial = True
        if persistence.revision == 0:
            raise ValueError("Historical merge requires a persisted checkpoint")
        for token, boundary in boundaries.items():
            builder = restored.candles[token]
            if boundary.tzinfo is None or boundary.utcoffset() is None:
                raise ValueError("Historical boundary must include a timezone")
            local = boundary.astimezone(IST)
            if (
                local.second != 0
                or local.microsecond != 0
                or local.minute % builder.minutes != 0
                or builder.current is not None
                or (
                    builder._closed_until is not None
                    and boundary < builder._closed_until
                )
            ):
                raise ValueError("Boundary must follow completed, aligned history")
        for token, boundary in boundaries.items():
            builder = restored.candles[token]
            # Also fence missing tail intervals: never recreate them from a
            # fragment of queued ticks. Recovery will fill them explicitly.
            builder._closed_until = boundary
            builder.last_time = boundary
        self.gaps.absorb(restored.gaps)
        restored.gaps = self.gaps
        # Commit fences before changing the live worker or releasing its queue.
        persistence.save(restored)
        if self.recorder is not None:
            self._record(
                "checkpoint",
                self.clock(),
                {
                    "checkpoint": persistence.snapshot(restored),
                    "configuration": persistence.configuration,
                },
            )
        self.candles = restored.candles
        self.closed_candles = restored.closed_candles
        self.candle_counts = restored.candle_counts
        self.gaps = restored.gaps
        self.persistence = persistence
        self.gap_required = _validated_revision is None
        persistence.save(self)
        self._history_ready.set()

    async def resume_validated_history(
        self,
        persistence: MarketPersistence,
        boundaries: dict[int, datetime],
        settings: Settings,
        calendar: SessionCalendar,
    ) -> None:
        """Managed handoff: validate sources, adopt, drain, then start entry hold.

        Caller owns the event loop and quiescent persistence writer. Diagnostic
        merge_history never grants eligibility. Any error requires a fresh worker.
        """
        self.resume_gate.revoke()
        self.resume_gate.delay = settings.readiness_entry_delay_seconds
        self.recovery_progress.begin()
        self.recovery_progress.stage("validating")
        invalid, dropped = self.invalid, self.dropped
        try:
            revision = validate_history(
                persistence, settings, calendar, self.clock(), boundaries
            )
            self.merge_history(persistence, boundaries, _validated_revision=revision)
            self.recovery_progress.stage("draining")
            drain = asyncio.create_task(self.queue.join())
            try:
                if self.task is None:
                    raise PersistenceError("Managed consumer must be running")
                await asyncio.wait(
                    [drain, self.task], return_when=asyncio.FIRST_COMPLETED
                )
                if self.task.done():
                    await self.task
                    raise PersistenceError("Managed consumer stopped during handoff")
                await drain
            finally:
                drain.cancel()
            if (
                self.invalid != invalid
                or self.dropped != dropped
                or not self._resume_health()
            ):
                raise PersistenceError("Queued live handoff failed quality validation")
            self.resume_gate.validated()
            self.recovery_progress.committed(
                {
                    t: self.closed_candles[t][-1].end
                    for t in self.tokens
                    if self.closed_candles[t]
                },
                quality_pending=any(
                    b.vwap_partial or (b.current is not None and b.current.partial)
                    for b in self.candles.values()
                ),
            )
        except BaseException as error:
            self.recovery_progress.failed(
                "cancelled"
                if isinstance(error, asyncio.CancelledError)
                else "handoff_failed"
            )
            self.resume_gate.revoke()
            self._history_ready.clear()
            raise

    def _resume_health(self) -> bool:
        now = self.clock()
        return (
            self.running
            and self.connected
            and self.task is not None
            and not self.task.done()
            and not self.exhausted
            and self._history_ready.is_set()
            and not self.gap_required
            and not self.gaps.snapshot()
            and self.queue.empty()
            and all(
                token in self.received
                and token in self.latest
                and 0 <= (now - self.received[token]).total_seconds() <= 5
                and abs((now - self.latest[token]["time"]).total_seconds()) <= 2
                for token in self.tokens
            )
        )

    def _entry_source_quality(self) -> bool:
        construction_gap = (
            self.persistence is not None
            and isinstance(self.persistence.renko, FiveMinuteCloseRenko)
            and self.persistence.renko.gap_detected
        )
        return not construction_gap and all(
            not builder.vwap_partial
            and (builder.current is None or not builder.current.partial)
            for builder in self.candles.values()
        )

    def entry_eligible(
        self,
        *,
        authenticated: bool = False,
        session_eligible: bool = False,
        indicators_ready: bool = False,
    ) -> bool:
        """Final callers must additionally enforce execution/risk/position rules."""
        return self.resume_gate.eligible(
            healthy=(
                self._resume_health()
                and self._entry_source_quality()
                and authenticated
                and session_eligible
                and indicators_ready
            )
        )

    def _accept(self, tick: dict[str, Any], received: datetime) -> None:
        if tick.get("instrument_token") in self.option_quotes.tokens:
            if self.option_quotes.accept(tick, received) and self.recorder is not None:
                quote = self.option_quotes.snapshot().get(tick["instrument_token"])
                if quote is not None:
                    self.recorder.write_option(received, quote.model_dump(mode="json"))
            return
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
            if self.calendar is not None and not any(
                s.opening <= ts < s.closing for s in self.calendar.sessions
            ):
                return
            fence = self.candles[token]._closed_until
            if fence is not None and ts < fence:
                self.history_overlap += 1
                return
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
            self.gaps.resume(token, ts)
            # Distinct updates in the same exchange second are legitimate.
            self.latest[token] = {
                "time": ts,
                "price": price,
                "volume": tick.get("volume_traded"),
                "oi": tick.get("oi"),
            }
            if (
                token in self.received
                and (received - self.received[token]).total_seconds() > 5
            ):
                self.resume_gate.revoke()
            self.received[token] = received
            self.accepted += 1
            if self.recorder is not None:
                self._record(
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
                        "gaps": self.gaps.snapshot(),
                    },
                )
            if self.persistence is not None:
                self.persistence.save(self)
        except (KeyError, TypeError, ValueError, OverflowError):
            self.resume_gate.revoke()
            self.invalid += 1

    def _store_candles(self, token: int, candles: list[MarketCandle]) -> None:
        self.closed_candles[token].extend(candles)
        self.candle_counts[token] += len(candles)

    def advance_candles(self, now: datetime | None = None) -> None:
        """Call after queued ticks drain, including at the end of the session."""
        at = now or self.clock()
        if not self._history_ready.is_set():
            raise ValueError("Cannot advance candles while historical merge is pending")
        if self.recorder is not None:
            self._record(
                "advance",
                at,
                {
                    "gap": self.gap_required,
                    "gaps": self.gaps.snapshot(),
                },
            )
        for token, builder in self.candles.items():
            if self.gap_required:
                builder.mark_gap()
            self._store_candles(token, builder.advance(at))
        if self.persistence is not None:
            self.persistence.save(self)

    def status(self) -> dict[str, Any]:
        now = self.clock()
        local = now.astimezone(IST)
        session = (
            any(s.opening <= local < s.closing for s in self.calendar.sessions)
            if self.calendar is not None
            else local.weekday() < 5 and time(9, 15) <= local.time() < time(15, 30)
        )
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
            "missing_ranges": self.gaps.snapshot(),
            "reconnect_exhausted": self.exhausted,
            "accepted": self.accepted,
            "history_pending": not self._history_ready.is_set(),
            "history_overlap": self.history_overlap,
            "invalid": self.invalid,
            "dropped": self.dropped,
            "queued": self.queue.qsize(),
            "connections": self.reconnects,
            "entries_enabled": False,
            "recovery": self.recovery_progress.snapshot(),
            "readiness": {
                **self.resume_gate.snapshot(
                    healthy=self._resume_health() and self._entry_source_quality()
                ),
                "construction_gap_detected": bool(
                    self.persistence is not None
                    and isinstance(self.persistence.renko, FiveMinuteCloseRenko)
                    and self.persistence.renko.gap_detected
                ),
            },
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

    async def drain(self) -> None:
        """Drain queued work or surface consumer failure."""
        if self.task is None:
            raise RuntimeError("Consumer is not running")
        drain = asyncio.create_task(self.queue.join())
        try:
            await asyncio.wait([drain, self.task], return_when=asyncio.FIRST_COMPLETED)
            if self.task.done():
                await self.task
                raise RuntimeError("Consumer stopped while draining")
            await drain
        finally:
            drain.cancel()

    async def stop(self) -> None:
        self.option_quotes.invalidate()
        self.running = False
        self.connected = False
        try:
            if self.task is not None:
                if not self.task.done() and self._history_ready.is_set():
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
            if self.persistence is not None and self.gaps.snapshot():
                self.persistence.save(self)
        finally:
            # SDK socket operations run on its Twisted reactor thread.
            self.option_quotes.invalidate()
            from twisted.internet import reactor

            reactor.callFromThread(self.socket.close)
            reactor.callFromThread(self.socket.stop_retry)
