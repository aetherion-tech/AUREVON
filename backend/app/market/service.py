"""One owned paper data worker, with explicit start/stop and scheduled checks."""

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, TypeVar

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.broker.instruments import Instruments
from app.broker.kite_auth import IST, AuthError, KiteAuth
from app.broker.kite_ticker import TickerWorker
from app.config import Settings
from app.db.models import Instrument
from app.market.exchange_calendar import ExchangeCalendar
from app.market.lifecycle_state import LifecycleStore, MarketEvents, ProcessLease
from app.market.persistence import MarketPersistence, PersistenceError
from app.market.recovery_progress import RecoveryProgress
from app.market.session_context import session_context
from app.market.tick_recording import TickRecorder
from app.market.warmup import SessionCalendar

T = TypeVar("T")


@dataclass(frozen=True)
class SelectedContract:
    spot: int
    future: int
    symbol: str
    expiry: str
    lot_size: int
    tick_size: str

    @property
    def identity(self) -> str:
        return f"NFO:{self.symbol}:{self.expiry}"


def select_contract(
    engine: Engine, instruments: Instruments, at: datetime
) -> SelectedContract:
    if not instruments.status()["ready"]:
        raise RuntimeError("Fresh NSE/NFO catalog required")
    with Session(engine) as db:
        spot = db.get(Instrument, ("NSE", "NIFTY 50"))
        futures = db.scalars(
            select(Instrument)
            .where(
                Instrument.exchange == "NFO",
                Instrument.name == "NIFTY",
                Instrument.instrument_type == "FUT",
                Instrument.expiry >= at.astimezone(IST).date(),
            )
            .order_by(Instrument.expiry, Instrument.tradingsymbol)
        ).all()
        if (
            spot is None
            or not futures
            or (len(futures) > 1 and futures[0].expiry == futures[1].expiry)
        ):
            raise RuntimeError("Unique current NIFTY spot/future required")
        future = futures[0]
        if (
            spot.instrument_token == future.instrument_token
            or future.expiry is None
            or future.lot_size <= 0
            or future.tick_size <= 0
        ):
            raise RuntimeError("Invalid contract metadata")
        return SelectedContract(
            spot.instrument_token,
            future.instrument_token,
            future.tradingsymbol,
            future.expiry.isoformat(),
            future.lot_size,
            str(future.tick_size),
        )


async def blocking(operation: Callable[[], T]) -> T:
    """Cancellation waits for synchronous work; clients/DB cannot be disposed early."""
    task = asyncio.create_task(asyncio.to_thread(operation))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise


class MarketService:
    def __init__(
        self,
        settings: Settings,
        auth: KiteAuth,
        engine: Engine,
        instruments: Instruments,
        *,
        clock: Callable[[], datetime] | None = None,
        pipeline: Callable[..., tuple[MarketPersistence, dict[int, datetime]]]
        | None = None,
        worker_factory: Callable[..., TickerWorker] = TickerWorker,
    ) -> None:
        self.settings, self.auth, self.engine, self.instruments = (
            settings,
            auth,
            engine,
            instruments,
        )
        self.clock = clock or (lambda: datetime.now(IST))
        self.calendar = ExchangeCalendar(settings.market_calendar_dir)
        self.lease = ProcessLease(settings.market_lock_file)
        self.facts = LifecycleStore(engine)
        self.events = MarketEvents()
        self.progress = RecoveryProgress()
        self.pipeline = pipeline or self.prepare
        self.worker_factory = worker_factory
        self.worker: TickerWorker | None = None
        self.selected: SelectedContract | None = None
        self.task: asyncio.Task[None] | None = None
        self.lock = asyncio.Lock()
        self.desired = settings.market_service_enabled
        self.closed = False
        self.day: str | None = None
        self.generation: str | None = None
        self.auth_checked: datetime | None = None
        self.reason = "stopped"
        self.retry_at: datetime | None = None
        self.failures = 0
        self.context: dict[str, Any] = {}

    async def open(self) -> None:
        if self.task is None:
            self.task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while not self.closed:
            await self.step()
            await asyncio.sleep(self.settings.market_poll_seconds)

    async def start(self) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("Service is closed")
        self.desired = True
        self.retry_at = None
        self.failures = 0
        await self.step()
        return self.status()

    async def stop(self) -> dict[str, Any]:
        async with self.lock:
            self.desired = False
            try:
                await self._stop_worker()
            finally:
                self.lease.release()
            self.reason = "stopped"
        return self.status()

    async def _stop_worker(self) -> None:
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.resume_gate.revoke()
            await worker.stop()

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.task is not None:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
        finally:
            await self.stop()

    async def step(self) -> None:
        async with self.lock:
            if not self.desired or self.closed:
                return
            try:
                self.lease.acquire()
                await self._step()
            except asyncio.CancelledError:
                await self._stop_worker()
                raise
            except Exception:
                # Fixed safe reason. Do not emit exception text or broker payloads.
                self.reason = "market_start_or_recovery_failed"
                self.progress.failed("handoff_failed")
                self.failures += 1
                self.retry_at = self.clock() + timedelta(
                    seconds=self.settings.recovery_backoff_max_seconds
                )
                await self._stop_worker()
            self.events.publish("recovery", self.progress.snapshot())
            self.events.publish(
                "service",
                {"state": self.reason, "day": self.day, "entries_enabled": False},
            )

    async def _step(self) -> None:
        now = self.clock().astimezone(IST)
        session = self.calendar.session(
            now
        )  # Missing calendar stops, never weekday fallback.
        self.events.publish(
            "session",
            {
                "day": now.date().isoformat(),
                "opening": session.opening if session else None,
                "closing": session.closing if session else None,
            },
        )
        if self.day != now.date().isoformat():
            await self._stop_worker()
            self.day = now.date().isoformat()
            self.selected = None
            self.context = {}
            self.failures = 0
            self.retry_at = None
            self.auth_checked = None
        if session is None or now >= session.closing:
            if self.worker is not None and self.worker._history_ready.is_set():
                await self.worker.drain()
                self.worker.advance_candles(now)
                if self.selected is not None and self.worker.persistence is not None:
                    context_stream, context_spot = (
                        self.worker.persistence.stream,
                        self.selected.spot,
                    )
                    self.context = await blocking(
                        lambda: session_context(
                            self.engine,
                            context_stream,
                            context_spot,
                            self.calendar.window(
                                now,
                                days=max(
                                    90, self.settings.warmup_lookback_trading_days * 3
                                ),
                            ),
                            now,
                        )
                    )
            await self._stop_worker()
            self.reason = "session_closed"
            return
        if now < session.opening - timedelta(minutes=15):
            self.reason = "before_preparation_window"
            return
        self.lease.acquire()
        local_session = await blocking(self.auth.managed_session)
        if local_session is None or local_session[1] <= now:
            await self._stop_worker()
            self.reason = "login_required"
            key = f"login_reminder:{self.day}"
            if not await blocking(lambda: self.facts.read(key)):
                await blocking(lambda: self.facts.write(key, {"at": now.isoformat()}))
                self.events.publish("login_required", {"day": self.day})
            return
        generation = local_session[0]
        if generation != self.generation:
            await self._stop_worker()
            self.lease.acquire()
            self.generation = generation
            self.auth_checked = None
            self.failures = 0
        if self.auth_checked is None or now - self.auth_checked >= timedelta(
            seconds=60
        ):
            verified = await blocking(self.auth.status)
            if not verified.authenticated:
                await self._stop_worker()
                self.reason = "login_required"
                return
            self.auth_checked = now
        if self.worker is None and (
            self.failures >= self.settings.recovery_max_attempts
            or (self.retry_at is not None and now < self.retry_at)
        ):
            self.reason = "recovery_retry_wait"
            return
        if not (await blocking(self.instruments.status))["ready"]:
            await self._stop_worker()
            self.lease.acquire()
            for attempt in range(self.settings.recovery_max_attempts):
                try:
                    await blocking(self.instruments.refresh)
                    break
                except Exception as error:
                    if isinstance(error, AuthError) and error.status_code in (401, 403):
                        raise
                    if attempt + 1 == self.settings.recovery_max_attempts:
                        raise
                    await asyncio.sleep(
                        min(
                            self.settings.recovery_backoff_seconds * 2**attempt,
                            self.settings.recovery_backoff_max_seconds,
                        )
                    )
        selected = await blocking(
            lambda: select_contract(self.engine, self.instruments, now)
        )
        if self.selected != selected:
            await self._stop_worker()
            self.lease.acquire()
            self.selected = selected
            self.context = {}
            self.failures = 0
            self.retry_at = None
            self.events.publish("contract_selected", asdict(selected))
        if now < session.opening:
            self.reason = "prepared_waiting_for_open"
            return
        if self.worker is not None:
            status = self.worker.status()
            self.events.publish(
                "quality",
                {
                    k: status[k]
                    for k in (
                        "stale",
                        "clock_or_feed_delay",
                        "gap_requires_replay",
                        "reconnect_exhausted",
                        "readiness",
                    )
                },
            )
            if (
                status["gap_requires_replay"]
                or status["reconnect_exhausted"]
                or (self.worker.task is not None and self.worker.task.done())
            ):
                await self._stop_worker()
            else:
                if status["stale"] or status["clock_or_feed_delay"]:
                    self.worker.resume_gate.revoke()
                await self.worker.drain()
                self.worker.advance_candles(now)
                if self.worker.persistence is not None:
                    context_stream = self.worker.persistence.stream
                    self.context = await blocking(
                        lambda: session_context(
                            self.engine,
                            context_stream,
                            selected.spot,
                            self.calendar.window(
                                now,
                                days=max(
                                    90, self.settings.warmup_lookback_trading_days * 3
                                ),
                            ),
                            now,
                        )
                    )
                self.reason = "running_entries_blocked"
                return
        if self.failures >= self.settings.recovery_max_attempts or (
            self.retry_at is not None and now < self.retry_at
        ):
            self.reason = "recovery_retry_wait"
            return
        self.lease.acquire()
        calendar = self.calendar.window(
            now, days=max(90, self.settings.warmup_lookback_trading_days * 3)
        )
        worker = self.worker_factory(
            await blocking(self.auth.create_ticker),
            selected.spot,
            selected.future,
            recorder=TickRecorder(
                self.settings.market_record_dir, selected.spot, selected.future
            ),
            clock=self.clock,
            calendar=calendar,
            recovery_progress=self.progress,
        )
        self.worker = worker
        await worker.start(buffer_only=True)
        for attempt in range(self.settings.recovery_max_attempts):
            cutoff = self.clock().astimezone(IST)
            store, boundaries = await blocking(
                lambda: self.pipeline(selected, calendar, cutoff)
            )
            latest = self.clock().astimezone(IST)
            if all(
                boundaries[t]
                == session.opening
                + ((latest - session.opening) // timedelta(minutes=m))
                * timedelta(minutes=m)
                for t, m in ((selected.spot, 1), (selected.future, 5))
            ):
                break
        else:
            raise PersistenceError("History catch-up could not reach a stable handoff")
        await worker.resume_validated_history(
            store, boundaries, self.settings, calendar
        )
        self.context = await blocking(
            lambda: session_context(
                self.engine, store.stream, selected.spot, calendar, self.clock()
            )
        )
        self.events.publish("context", self.context)
        self.reason = "running_entries_blocked"

    def prepare(
        self, selected: SelectedContract, calendar: SessionCalendar, now: datetime
    ) -> tuple[MarketPersistence, dict[int, datetime]]:
        from app.market.context_history import fetch_context_history
        from app.market.history_renko import rebuild_historical_renko
        from app.market.recording_recovery import reconcile_recording
        from app.market.recovery import recover_missing_history
        from app.market.spot_history import fetch_spot_history
        from app.market.warmup import plan_history

        if (
            self.settings.renko_anchor is None
            or self.settings.renko_mode != "minute_close"
        ):
            raise PersistenceError("Managed pipeline requires minute-close anchor")
        identity = hashlib.sha256(
            json.dumps(asdict(selected), sort_keys=True).encode()
        ).hexdigest()[:16]
        stream = f"{self.settings.market_stream}:{identity}"
        store = MarketPersistence(
            self.engine,
            stream,
            selected.spot,
            selected.future,
            box=self.settings.renko_box,
            anchor=self.settings.renko_anchor,
        )
        scratch = TickerWorker(
            None,
            selected.spot,
            selected.future,
            recorder=TickRecorder(
                self.settings.market_record_dir, selected.spot, selected.future
            ),
            calendar=calendar,
        )
        if store.restore(scratch):
            scratch.persistence = store
            if scratch.recording_cursor is not None:
                reconcile_recording(scratch)
            recover_missing_history(
                self.auth,
                self.engine,
                self.settings,
                stream,
                selected.spot,
                selected.future,
                selected.identity,
                calendar,
                now,
                correct_partial=True,
                progress=self.progress,
            )
        else:
            self.progress.begin()
            plan = plan_history(self.settings, calendar, now)
            self.progress.stage("downloading")
            fetch_spot_history(self.auth, self.engine, stream, selected.spot, plan)
            fetch_context_history(
                self.auth,
                self.engine,
                stream,
                selected.symbol,
                plan,
                calendar,
            )
            self.progress.stage("rebuilding")
            rebuild_historical_renko(
                self.engine,
                self.settings,
                stream,
                selected.spot,
                selected.future,
                selected.identity,
                plan,
                calendar,
            )
        session = next(s for s in calendar.sessions if s.opening <= now < s.closing)
        return store, {
            token: session.opening
            + ((now - session.opening) // timedelta(minutes=minutes))
            * timedelta(minutes=minutes)
            for token, minutes in ((selected.spot, 1), (selected.future, 5))
        }

    def status(self) -> dict[str, Any]:
        return {
            "state": self.reason,
            "desired": self.desired,
            "selected": asdict(self.selected) if self.selected else None,
            "worker": self.worker.status() if self.worker else None,
            "recovery": self.progress.snapshot(),
            "context": self.context,
            "events_sequence": self.events.sequence,
            "entries_enabled": False,
        }
