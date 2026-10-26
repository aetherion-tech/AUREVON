"""Managed lifecycle acceptance: fake broker/socket, actual SQLite/recovery paths."""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.broker.instruments import Instruments
from app.broker.kite_auth import IST, KiteAuth, KiteStatus
from app.broker.kite_ticker import TickerWorker
from app.config import Settings
from app.db.models import Base, Instrument, InstrumentSnapshot, MarketCheckpoint
from app.db.session import database_engine
from app.market.service import MarketService, blocking

NOW = datetime(2026, 10, 23, 11, 0, tzinfo=IST)


@pytest.fixture
def managed(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'service.db').as_posix()}",
        market_record_dir=tmp_path / "ticks",
        market_lock_file=tmp_path / "owner.lock",
        warmup_lookback_trading_days=1,
        renko_anchor=100,
        renko_box=10,
        recovery_max_attempts=2,
        recovery_backoff_seconds=0.001,
        recovery_backoff_max_seconds=0.01,
    )
    engine = database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    wall = [NOW]
    with Session(engine) as db, db.begin():
        for exchange, symbol, token, expiry, kind in (
            ("NSE", "NIFTY 50", 111, None, "EQ"),
            ("NFO", "NIFTYTESTFUT", 222, date(2026, 10, 29), "FUT"),
        ):
            db.add(
                Instrument(
                    exchange=exchange,
                    tradingsymbol=symbol,
                    instrument_token=token,
                    name="NIFTY",
                    expiry=expiry,
                    strike=0,
                    tick_size=0.05,
                    lot_size=65,
                    instrument_type=kind,
                    segment=exchange,
                )
            )
            db.add(InstrumentSnapshot(exchange=exchange, loaded_at=NOW, row_count=1))
    auth = Mock(spec=KiteAuth)
    auth.managed_session.return_value = ("generation-a", NOW + timedelta(days=1))
    auth.status.return_value = KiteStatus(
        configured=True, authenticated=True, message="fixture"
    )

    def historical(token, interval, start, end, oi=False):
        step = (
            timedelta(days=1)
            if interval == "day"
            else timedelta(minutes=1 if interval == "minute" else 5)
        )
        rows = []
        stamp = start
        while stamp <= end:
            if stamp.weekday() < 5:
                price = Decimal(100 + (stamp.minute % 4) * 10)
                row = [
                    stamp.isoformat(),
                    str(price),
                    str(price),
                    str(price),
                    str(price),
                    "10",
                ]
                if oi:
                    row.append("50")
                rows.append(row)
            stamp += step
        return {"candles": rows}

    auth.historical_data.side_effect = historical
    auth.create_ticker.side_effect = lambda: Mock()
    workers = []

    def factory(socket, *tokens, **kwargs):
        worker = TickerWorker(socket, *tokens, **kwargs)

        def connected(threaded=True):
            worker._connected()
            for token in tokens:
                worker._enqueue(
                    [
                        {
                            "instrument_token": token,
                            "exchange_timestamp": wall[0],
                            "last_price": 150,
                            "volume_traded": 100,
                            "oi": 50,
                        }
                    ],
                    wall[0],
                )

        socket.connect.side_effect = connected
        workers.append(worker)
        return worker

    instruments = Instruments(engine, auth, clock=lambda: wall[0])
    service = MarketService(
        settings,
        auth,
        engine,
        instruments,
        clock=lambda: wall[0],
        worker_factory=factory,
    )
    with patch("twisted.internet.reactor.callFromThread") as reactor:
        yield service, wall, auth, workers, reactor
    engine.dispose()


@pytest.mark.asyncio
async def test_owned_cold_start_duplicate_start_stop_and_scheduler(managed):
    service, wall, auth, workers, reactor = managed
    try:
        await service.open()
        task = service.task
        await service.open()
        assert service.task is task
        result = await service.start()
        assert result["state"] == "running_entries_blocked", result
        assert service.worker.accepted == 2
        assert not service.worker.gap_required
        await service.start()
        assert len(workers) == 1 and auth.create_ticker.call_count == 1
        assert service.context["opening_range"]["state"] == "complete"
        assert service.context["previous_close"] is not None
        assert result["entries_enabled"] is False
        await service.stop()
        await service.stop()
        assert service.worker is None
        assert reactor.call_count == 2
    finally:
        await service.close()
    assert service.task.done() and service.lease.stream is None


@pytest.mark.asyncio
async def test_expiry_relogin_and_real_recovery_before_resuming(managed):
    service, wall, auth, workers, _ = managed
    try:
        await service.start()
        assert service.worker is not None, service.status()
        first = service.worker
        auth.managed_session.return_value = None
        await service.step()
        assert service.worker is None and service.reason == "login_required"
        await service.step()
        reminders = [e for e in service.events.events if e["kind"] == "login_required"]
        assert len(reminders) == 1
        wall[0] += timedelta(minutes=5)
        auth.managed_session.return_value = (
            "generation-b",
            wall[0] + timedelta(hours=2),
        )
        await service.step()
        assert service.worker is not None, service.status()
        assert service.worker is not first and len(workers) == 2
        assert service.worker.resume_gate.started is not None
        with Session(service.engine) as db:
            checkpoint = db.scalars(select(MarketCheckpoint)).first()
            import json

            state = json.loads(checkpoint.state)
            assert state["validated_recovery"]["unfinished_live_bucket_partial"] is True
            assert state["validated_recovery"]["retired_gaps"]
        assert service.status()["entries_enabled"] is False
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_token_change_replaces_worker_with_distinct_stream(managed):
    service, _, _, workers, _ = managed
    try:
        await service.start()
        first_stream = service.worker.persistence.stream
        with Session(service.engine) as db, db.begin():
            db.get(Instrument, ("NFO", "NIFTYTESTFUT")).instrument_token = 333
        await service.step()
        assert service.worker is not None, service.status()
        assert len(workers) == 2 and service.selected.future == 333
        assert service.worker.persistence.stream != first_stream
        assert not workers[0].running
    finally:
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cause", ["market_close", "missing_calendar", "stale_catalog", "failed_warmup"]
)
async def test_fail_closed_service_paths(managed, tmp_path, cause):
    service, wall, auth, _, _ = managed
    try:
        if cause == "market_close":
            await service.start()
            wall[0] = wall[0].replace(hour=15, minute=30)
        elif cause == "missing_calendar":
            service.calendar.directory = tmp_path / "missing"
        elif cause == "stale_catalog":
            with Session(service.engine) as db, db.begin():
                for item in db.scalars(select(InstrumentSnapshot)):
                    item.loaded_at = NOW - timedelta(days=1)
            auth.download_instruments.side_effect = RuntimeError("private secret")
        else:
            service.pipeline = Mock(side_effect=RuntimeError("private secret"))
        await service.start()
        assert service.worker is None
        assert service.status()["entries_enabled"] is False
        assert "private secret" not in str(service.status())
        if cause == "stale_catalog":
            assert auth.download_instruments.call_count == 2
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_cancellation_joins_synchronous_work_before_disposal():
    from threading import Event

    entered, release, finished = Event(), Event(), Event()

    def operation():
        entered.set()
        assert release.wait(5)
        finished.set()

    task = asyncio.create_task(blocking(operation))
    await asyncio.to_thread(entered.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


@pytest.mark.asyncio
async def test_day_rollover_requires_new_catalog_and_preserves_recordings(managed):
    service, wall, auth, _, _ = managed
    try:
        await service.start()
        assert service.worker is not None
        files = list(service.settings.market_record_dir.rglob("*.jsonl"))
        before = {p: p.read_bytes() for p in files}
        wall[0] = wall[0] + timedelta(days=3)
        auth.managed_session.return_value = ("new-day", wall[0] + timedelta(hours=1))
        auth.download_instruments.side_effect = RuntimeError("unavailable")
        await service.step()
        assert service.worker is None
        assert service.context == {}
        assert all(p.read_bytes() == data for p, data in before.items())
        assert service.status()["entries_enabled"] is False
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_persisted_login_reminder_is_not_duplicated_after_restart(managed):
    service, wall, auth, _, _ = managed
    other = None
    try:
        auth.managed_session.return_value = None
        await service.start()
        assert (
            len([e for e in service.events.events if e["kind"] == "login_required"])
            == 1
        )
        await service.close()
        other = MarketService(
            service.settings,
            auth,
            service.engine,
            service.instruments,
            clock=lambda: wall[0],
        )
        await other.start()
        assert other.reason == "login_required"
        assert not [e for e in other.events.events if e["kind"] == "login_required"]
    finally:
        await service.close()
        if other:
            await other.close()


@pytest.mark.asyncio
async def test_catalog_transient_retry_then_freshness_gate(managed):
    service, wall, auth, _, _ = managed

    try:
        with Session(service.engine) as db, db.begin():
            for row in db.scalars(select(InstrumentSnapshot)):
                row.loaded_at = NOW - timedelta(days=1)
        calls = []

        def refresh():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("temporary transport")
            with Session(service.engine) as db, db.begin():
                for row in db.scalars(select(InstrumentSnapshot)):
                    row.loaded_at = wall[0]
            return service.instruments.status()

        with patch.object(service.instruments, "refresh", side_effect=refresh):
            await service.start()
        assert len(calls) == 2
        assert service.worker is not None, service.status()
        kinds = {event["kind"] for event in service.events.events}
        assert {"session", "contract_selected", "recovery", "service"} <= kinds
    finally:
        await service.close()


def test_app_lifespan_owns_service_with_no_default_broker_calls(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings = Settings(
        _env_file=None, database_url=f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    )
    auth = Mock(spec=KiteAuth)
    app = create_app(settings, auth)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        service = app.state.market_service
        assert service.task is not None and not service.task.done()
        auth.managed_session.assert_not_called()
        auth.create_ticker.assert_not_called()
    assert service.closed and service.task.done()
    auth.close.assert_called_once()
