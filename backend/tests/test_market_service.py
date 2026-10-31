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


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [0, 1])
async def test_login_auto_prepares_chart_without_start_or_paper_poll(managed, days):
    from app.api.event_hub import EventHub
    from app.api.live_service import LiveService

    service, wall, auth, workers, _ = managed
    service.settings.local_ui_enabled = True
    wall[0] = NOW + timedelta(days=days)
    auth.managed_session.return_value = ("logged-in", wall[0] + timedelta(days=1))
    service.paper_poll = Mock(side_effect=AssertionError("No paper actions"))
    try:
        assert not service.desired
        await service.step()
        snap = LiveService(service, service.engine, EventHub()).sample()
        assert snap.latest_brick is not None
        assert snap.context["chart_display_mode"] == "historical"
        assert not snap.desired and not snap.entries_enabled
        assert service.worker is None and workers == []
        assert service.lease.stream is None
        auth.create_ticker.assert_not_called()
        service.paper_poll.assert_not_called()
        auth.historical_data.reset_mock()
        auth.status.reset_mock()
        await service.step()
        auth.historical_data.assert_not_called()
        auth.status.assert_not_called()
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_auto_chart_requires_login_and_bounds_failed_downloads(managed):
    service, wall, auth, workers, _ = managed
    service.settings.local_ui_enabled = True
    auth.managed_session.return_value = None
    try:
        await service.step()
        auth.historical_data.assert_not_called()
        auth.managed_session.return_value = ("first", wall[0] + timedelta(days=1))
        auth.historical_data.side_effect = RuntimeError("private broker error")
        await service.step()
        assert service.reason == "chart_history_unavailable"
        assert service.cached_closed_chart() is None
        calls = auth.historical_data.call_count
        await service.step()
        assert auth.historical_data.call_count == calls
        auth.managed_session.return_value = ("new-login", wall[0] + timedelta(days=1))
        await service.step()
        assert auth.historical_data.call_count > calls
        assert not service.desired and workers == []
    finally:
        await service.close()


@pytest.fixture
def managed(tmp_path, request):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'service.db').as_posix()}",
        market_record_dir=tmp_path / "ticks",
        market_lock_file=tmp_path / "owner.lock",
        warmup_lookback_trading_days=1,
        renko_anchor=100,
        renko_box=10,
        renko_source_minutes=getattr(request, "param", 1),
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
@pytest.mark.parametrize("managed", [1, 5], indirect=True)
async def test_closed_history_cache_projection_without_socket_or_entry_permission(
    managed,
):
    import json

    from app.api.event_hub import EventHub
    from app.api.live_service import LiveService

    service, wall, auth, workers, _ = managed
    service.settings.local_ui_enabled = True
    wall[0] = NOW + timedelta(days=1)
    auth.managed_session.return_value = ("weekend", wall[0] + timedelta(days=1))
    with Session(service.engine) as db, db.begin():
        db.add(
            MarketCheckpoint(
                stream="retained-observation",
                revision=7,
                configuration='{"retained":true}',
                state='{"do_not_change":true}',
            )
        )
    other = None
    try:
        result = await service.start()
        assert result["state"] == "session_closed_historical", result
        assert service.worker is None and workers == []
        auth.create_ticker.assert_not_called()
        assert all(
            c.args[0] == 111 and c.args[1] == "minute"
            for c in auth.historical_data.call_args_list
        )
        live = LiveService(service, service.engine, EventHub())
        live.domain_sample = lambda: {
            "entries_enabled": True,
            "signals": [],
            "unavailable": [],
        }
        snap = live.sample()
        assert snap.context["chart_display_mode"] == "historical"
        assert (
            snap.context["historical_as_of"]
            == NOW.replace(hour=15, minute=30).isoformat()
        )
        assert snap.quality.stale and not snap.quality.connected
        assert not snap.entries_enabled and snap.ticks == []
        assert snap.latest_brick is not None
        assert {"indicators", "signals"} <= set(snap.unavailable)
        page = live.bricks(snap.stream, -1, 300, None)
        assert page.items and page.configuration["scope"] == "SPOT_ONLY_DISPLAY"
        assert page.configuration["future"] is None
        assert (
            page.configuration["source_minutes"]
            == service.settings.renko_source_minutes
        )
        assert all(b.ts <= NOW.replace(hour=15, minute=30) for b in page.items)
        with Session(service.engine) as db:
            retained = db.get(MarketCheckpoint, "retained-observation")
            assert (
                retained.revision == 7 and json.loads(retained.state)["do_not_change"]
            )
        auth.historical_data.reset_mock()
        auth.status.reset_mock()
        auth.managed_session.return_value = None
        with patch(
            "app.market.closed_history.consume_spot",
            side_effect=AssertionError("No read-time recalculation"),
        ):
            await service.step()
            assert live.sample().stream == snap.stream
        auth.historical_data.assert_not_called()
        auth.status.assert_not_called()
        await service.close()
        # Read-only cache remains available across app restart without login/start.
        other = MarketService(
            service.settings,
            auth,
            service.engine,
            service.instruments,
            clock=lambda: wall[0],
        )
        cached = LiveService(other, service.engine, EventHub()).sample()
        assert cached.stream == snap.stream and cached.latest_brick == snap.latest_brick
        assert cached.context["chart_display_mode"] == "historical"
        assert cached.quality.stale and not cached.entries_enabled
        assert {"execution", "positions", "wallet", "pnl"} <= set(cached.unavailable)
        auth.historical_data.assert_not_called()
    finally:
        await service.close()
        if other:
            await other.close()


@pytest.mark.asyncio
async def test_corrupt_closed_display_is_not_overwritten_or_refetched(managed):
    from app.db.models import StoredBrick

    service, wall, auth, _, _ = managed
    service.settings.local_ui_enabled = True
    wall[0] = NOW + timedelta(days=1)
    auth.managed_session.return_value = ("weekend", wall[0] + timedelta(days=1))
    try:
        await service.start()
        chart = service.cached_closed_chart()
        assert chart is not None
        with Session(service.engine) as db, db.begin():
            row = db.get(StoredBrick, (chart.stream, 0))
            row.payload = '{"tampered":true}'
        auth.historical_data.reset_mock()
        await service.step()
        assert service.cached_closed_chart() is None
        auth.historical_data.assert_not_called()
        with Session(service.engine) as db:
            assert db.get(StoredBrick, (chart.stream, 0)).payload == '{"tampered":true}'
        assert not service.status()["entries_enabled"]
    finally:
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("managed", [5], indirect=True)
async def test_closed_to_live_clears_historical_display_metadata(managed):
    from app.api.event_hub import EventHub
    from app.api.live_service import LiveService

    service, wall, auth, _, _ = managed
    service.settings.local_ui_enabled = True
    wall[0] = NOW + timedelta(days=1)
    auth.managed_session.return_value = ("weekend", wall[0] + timedelta(days=1))
    try:
        await service.start()
        live = LiveService(service, service.engine, EventHub())
        archived = live.sample()
        assert archived.context["chart_display_mode"] == "historical"
        wall[0] = NOW + timedelta(days=3)
        auth.managed_session.return_value = ("monday", wall[0] + timedelta(days=1))
        with Session(service.engine) as db, db.begin():
            for row in db.scalars(select(InstrumentSnapshot)):
                row.loaded_at = wall[0]
        await service.start()
        assert service.worker is not None, service.status()
        current = live.sample()
        assert current.stream != archived.stream
        assert "chart_display_mode" not in current.context
        assert "historical_as_of" not in current.context
        assert current.quality.connected and not current.quality.stale
        assert current.ticks and current.latest_brick is not None
        assert not current.entries_enabled
    finally:
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["login", "missing_minute", "broker"])
async def test_closed_history_failure_does_not_publish_or_start_socket(
    managed, failure
):
    from app.db.models import StoredBrick

    service, wall, auth, workers, _ = managed
    service.settings.local_ui_enabled = True
    wall[0] = NOW + timedelta(days=1)
    auth.managed_session.return_value = ("weekend", wall[0] + timedelta(days=1))
    original = auth.historical_data.side_effect
    if failure == "login":
        auth.managed_session.return_value = None
    elif failure == "broker":
        auth.historical_data.side_effect = RuntimeError("fixture")
    else:

        def missing(*args, **kwargs):
            result = original(*args, **kwargs)
            result["candles"] = result["candles"][1:]
            return result

        auth.historical_data.side_effect = missing
    try:
        await service.start()
        assert service.worker is None and workers == []
        assert service.cached_closed_chart() is None
        assert not service.status()["entries_enabled"]
        auth.create_ticker.assert_not_called()
        if failure == "login":
            auth.historical_data.assert_not_called()
        with Session(service.engine) as db:
            assert db.scalars(select(StoredBrick)).all() == []
            assert db.scalars(select(MarketCheckpoint)).all() == []
    finally:
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("managed", [5], indirect=True)
async def test_five_minute_managed_history_live_ui_restart_and_profile_fence(managed):
    import json

    from app.api.event_hub import EventHub
    from app.api.live_service import LiveService
    from app.market.five_minute_renko import FiveMinuteCloseRenko
    from app.market.persistence import PersistenceError

    service, wall, auth, workers, _ = managed
    try:
        result = await service.start()
        assert result["state"] == "running_entries_blocked", result
        worker = service.worker
        store = worker.persistence
        assert isinstance(store.renko, FiveMinuteCloseRenko)
        assert store.stream.endswith(":5m-close-wicks-v2")
        assert json.loads(store.configuration)["source_minutes"] == 5
        live = LiveService(service, service.engine, EventHub())
        initial = live.sample()
        assert initial.latest_brick is not None and not initial.entries_enabled
        before = initial.latest_brick.index
        origin = wall[0]
        for i in range(1, 11):
            wall[0] = origin + timedelta(minutes=i)
            for token in worker.tokens:
                worker._accept(
                    {
                        "instrument_token": token,
                        "exchange_timestamp": wall[0],
                        "last_price": 100 + (i % 4) * 10,
                        "volume_traded": 100 + i * 10,
                        "oi": 50,
                    },
                    wall[0],
                )
        assert worker.invalid == 0
        assert not worker.gap_required
        assert worker.status()["readiness"]["construction_gap_detected"] is True
        assert not worker._entry_source_quality()
        await service.step()
        assert service.worker is worker  # known partial prefix must not loop reconnects
        snapshot = live.sample()
        assert snapshot.latest_brick.index > before
        page = live.bricks(snapshot.stream, before, 300, None)
        assert page.items and page.configuration["source_minutes"] == 5
        assert all(
            b.wick_high is not None and b.wick_low is not None for b in page.items
        )
        assert not snapshot.entries_enabled
        await service.stop()
        # Fresh owner takes the real recovery/validated-handoff path.
        await service.start()
        assert service.worker is None
        assert service.reason == "history_waiting_for_completed_bucket"
        assert service.failures == 0
        deadline = service.retry_at
        assert deadline > wall[0]
        await service.step()
        assert service.failures == 0 and len(workers) == 2
        wall[0] = deadline
        await service.step()
        assert service.worker is not None, service.status()
        assert service.worker.persistence.stream == store.stream
        assert len(workers) == 3
        assert (
            service.worker.status()["readiness"]["construction_gap_detected"] is False
        )
        assert not service.status()["entries_enabled"]
        from app.market.construction import managed_store

        legacy = service.settings.model_copy(update={"renko_source_minutes": 1})
        calendar = service.calendar.window(wall[0])
        old = managed_store(service.engine, legacy, store.stream, 111, 222, calendar)
        with pytest.raises(PersistenceError, match="configuration"):
            TickerWorker(None, 111, 222, persistence=old)
    finally:
        await service.close()


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
async def test_explicit_local_ui_without_anchor_streams_quotes_without_fake_chart(
    managed,
):
    service, wall, auth, workers, reactor = managed
    service.settings.local_ui_enabled = True
    service.settings.renko_anchor = None
    service.pipeline = Mock(
        side_effect=AssertionError("Quote-only mode cannot invent a grid")
    )
    try:
        result = await service.start()
        assert result["state"] == "running_quotes_only_anchor_required"
        assert service.worker.accepted == 2
        assert service.worker.persistence is None
        assert service.worker.resume_gate.started is None
        assert service.context["quote_only"] is True
        assert result["entries_enabled"] is False
        await service.step()
        assert len(workers) == 1
        service.pipeline.assert_not_called()
    finally:
        await service.close()


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
