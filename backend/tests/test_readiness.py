"""Validated managed handoff uses synthetic candles, fake clocks and SQLite."""

import json
from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session as DBSession

from app.broker.kite_auth import IST
from app.broker.kite_ticker import TickerWorker
from app.config import Settings
from app.db.models import Base, MarketCheckpoint, StoredBrick, StoredCandle
from app.db.session import database_engine
from app.market.candles_5m import MarketCandle
from app.market.persistence import MarketPersistence, encode
from app.market.readiness import ResumeGate, validate_history
from app.market.warmup import Session, SessionCalendar

OPEN = datetime(2026, 10, 23, 9, 15, tzinfo=IST)
NOW = OPEN + timedelta(minutes=105)
SETTINGS = Settings(
    _env_file=None, warmup_lookback_trading_days=1, renko_box=10, renko_anchor=100
)
CALENDAR = SessionCalendar(
    date(2026, 10, 22),
    date(2026, 10, 23),
    (
        Session(
            OPEN - timedelta(days=1), OPEN - timedelta(days=1) + timedelta(minutes=105)
        ),
        Session(OPEN, OPEN + timedelta(minutes=375)),
    ),
)
BOUNDARIES = {111: NOW, 222: NOW}


@pytest.fixture
def prepared(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'readiness.db').as_posix()}")
    Base.metadata.create_all(engine)
    store = MarketPersistence(engine, "test", 111, 222, box=10, anchor=100)
    seed = TickerWorker(None, 111, 222)
    with DBSession(engine) as db, db.begin():
        for session in CALENDAR.sessions:
            for token, minutes in ((111, 1), (222, 5)):
                for minute in range(0, 105, minutes):
                    start = session.opening + timedelta(minutes=minute)
                    price = Decimal(100 + minute * 10)
                    candle = MarketCandle(
                        start,
                        start + timedelta(minutes=minutes),
                        price,
                        price,
                        price,
                        price,
                        Decimal(10) if token == 222 else None,
                        Decimal(50) if token == 222 else None,
                        False,
                    )
                    candle = seed.candles[token].import_completed(
                        candle,
                        session_open=session.opening,
                        session_close=session.closing,
                        cutoff=NOW,
                    )
                    seed.candle_counts[token] += 1
                    db.add(
                        StoredCandle(
                            stream="test",
                            token=token,
                            time=start.astimezone(
                                __import__("datetime").UTC
                            ).isoformat(),
                            payload=encode(asdict(candle)),
                        )
                    )
                    if token == 111:
                        for brick in store.renko.on_price(price, candle.end):
                            db.add(
                                StoredBrick(
                                    stream="test",
                                    index=brick.index,
                                    payload=encode(asdict(brick)),
                                )
                            )
        db.add(
            MarketCheckpoint(
                stream="test",
                revision=1,
                configuration=store.configuration,
                state=encode(store.snapshot(seed)),
            )
        )
    yield engine, store
    engine.dispose()


def test_valid_history_is_read_only(prepared):
    engine, store = prepared
    assert validate_history(store, SETTINGS, CALENDAR, NOW, BOUNDARIES) == 1
    with DBSession(engine) as db:
        assert db.get(MarketCheckpoint, "test").revision == 1


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "partial",
        "oi",
        "vwap",
        "bricks",
        "builder",
        "gap",
        "recovery",
        "active",
    ],
)
def test_bad_history_cannot_release_handoff(prepared, damage):
    engine, store = prepared
    with DBSession(engine) as db, db.begin():
        checkpoint = db.get(MarketCheckpoint, "test")
        state = json.loads(checkpoint.state)
        if damage in ("missing", "partial", "oi", "vwap"):
            from sqlalchemy import select

            row = db.scalars(
                select(StoredCandle).where(StoredCandle.token == 222)
            ).first()
            if damage == "missing":
                db.delete(row)
            else:
                payload = json.loads(row.payload)
                payload[damage] = (
                    True
                    if damage == "partial"
                    else (None if damage == "oi" else "99999")
                )
                row.payload = encode(payload)
        elif damage == "bricks":
            db.get(StoredBrick, ("test", 0)).payload = "{}"
        elif damage == "builder":
            state["builders"]["222"]["weighted"] = "123"
        elif damage == "active":
            state["builders"]["222"]["current"] = {}
        elif damage == "gap":
            state["gaps"] = [
                {
                    "token": 111,
                    "reason": "disconnect",
                    "start": str(OPEN),
                    "resume_after": str(NOW + timedelta(minutes=5)),
                    "end": None,
                }
            ]
        else:
            state["recovery"] = {"oi_missing": 1}
        checkpoint.state = encode(state)
    with pytest.raises((ValueError, RuntimeError)):
        validate_history(store, SETTINGS, CALENDAR, NOW, BOUNDARIES)
    with DBSession(engine) as db:
        assert db.get(MarketCheckpoint, "test").revision == 1


def test_delay_revoke_restart_and_backward_clock():
    time = [0.0]
    gate = ResumeGate(60, lambda: time[0])
    assert not gate.eligible(healthy=True)
    gate.validated()
    time[0] = 59.999
    assert not gate.eligible(healthy=True)
    time[0] = 60
    assert gate.eligible(healthy=True)
    assert not gate.eligible(healthy=False)
    time[0] = 500
    assert not gate.eligible(healthy=True)
    gate.validated()
    time[0] = 499
    assert not gate.eligible(healthy=True)
    time[0] = 1000
    assert not gate.eligible(healthy=True)
    assert not ResumeGate(60, lambda: time[0]).eligible(healthy=True)


@pytest.mark.asyncio
async def test_managed_handoff_delay_and_new_gap(prepared):
    _, store = prepared
    elapsed = [0.0]
    wall = [NOW]
    worker = TickerWorker(
        Mock(), 111, 222, clock=lambda: wall[0], elapsed_clock=lambda: elapsed[0]
    )
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        try:
            worker.connected = True
            for token in worker.tokens:
                worker._enqueue(
                    [
                        {
                            "instrument_token": token,
                            "exchange_timestamp": NOW,
                            "last_price": 200,
                            "volume_traded": 100,
                            "oi": 50,
                        }
                    ],
                    NOW,
                )
            await worker.resume_validated_history(store, BOUNDARIES, SETTINGS, CALENDAR)
            assert not worker.resume_gate.eligible(healthy=True)
            elapsed[0] = 60
            assert worker.resume_gate.eligible(healthy=True)
            # The first live volume fragment is still partial: elapsed time alone
            # must not authorize an entry, even with external gates satisfied.
            assert not worker.entry_eligible(
                authenticated=True, session_eligible=True, indicators_ready=True
            )
            assert not worker.entry_eligible()  # No auth/session/indicator bypass.
            worker._track_gap("disconnect", NOW)
            elapsed[0] = 120
            assert not worker.entry_eligible(
                authenticated=True, session_eligible=True, indicators_ready=True
            )
        finally:
            await worker.stop()


@pytest.mark.asyncio
async def test_invalid_boundary_keeps_queue_blocked(prepared):
    _, store = prepared
    worker = TickerWorker(Mock(), 111, 222, clock=lambda: NOW)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        try:
            with pytest.raises(RuntimeError):
                await worker.resume_validated_history(
                    store,
                    {111: NOW + timedelta(minutes=1), 222: NOW},
                    SETTINGS,
                    CALENDAR,
                )
            assert not worker._history_ready.is_set()
            assert worker.resume_gate.started is None
        finally:
            await worker.stop()


@pytest.mark.parametrize("delay", [60, 120, 3600])
def test_configured_delay_boundary(delay):
    clock = [10.0]
    gate = ResumeGate(delay, lambda: clock[0])
    gate.validated()
    clock[0] = 10 + delay - 0.001
    assert not gate.eligible(healthy=True)
    clock[0] = 10 + delay
    assert gate.eligible(healthy=True)


@pytest.mark.asyncio
async def test_invalid_queued_tick_never_starts_delay(prepared):
    _, store = prepared
    worker = TickerWorker(Mock(), 111, 222, clock=lambda: NOW)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        worker.connected = True
        worker._enqueue(
            [{"instrument_token": 111, "exchange_timestamp": NOW, "last_price": -1}],
            NOW,
        )
        try:
            with pytest.raises(RuntimeError, match="quality validation"):
                await worker.resume_validated_history(
                    store, BOUNDARIES, SETTINGS, CALENDAR
                )
            assert worker.resume_gate.started is None
            assert not worker._history_ready.is_set()
        finally:
            await worker.stop()


def test_changed_settings_are_not_accepted(prepared):
    _, store = prepared
    with pytest.raises(RuntimeError, match="settings"):
        validate_history(
            store,
            SETTINGS.model_copy(update={"renko_box": 20}),
            CALENDAR,
            NOW,
            BOUNDARIES,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["revision_race", "commit_rollback"])
async def test_validation_to_handoff_failure_keeps_processing_blocked(
    prepared, failure
):
    engine, store = prepared
    worker = TickerWorker(Mock(), 111, 222, clock=lambda: NOW)
    original = validate_history

    def raced(*args, **kwargs):
        checked = original(*args, **kwargs)
        with DBSession(engine) as db, db.begin():
            db.get(MarketCheckpoint, "test").revision += 1
        return checked

    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start(buffer_only=True)
        try:
            if failure == "revision_race":
                context = patch(
                    "app.broker.kite_ticker.validate_history", side_effect=raced
                )
            else:
                context = patch.object(
                    store, "save", side_effect=RuntimeError("private failure detail")
                )
            with context:
                with pytest.raises(RuntimeError):
                    await worker.resume_validated_history(
                        store, BOUNDARIES, SETTINGS, CALENDAR
                    )
            assert not worker._history_ready.is_set()
            assert worker.accepted == 0
            status = worker.status()
            assert status["recovery"]["phase"] == "failed"
            assert status["recovery"]["failure_reason"] == "handoff_failed"
            assert status["readiness"]["state"] == "awaiting_validation"
            assert "private failure detail" not in str(status)
        finally:
            await worker.stop()


def test_readiness_snapshot_does_not_advance_or_enable_gate():
    clock = [0.0]
    gate = ResumeGate(60, lambda: clock[0])
    gate.validated()
    clock[0] = 20
    state = gate.snapshot(healthy=True)
    assert state["remaining_seconds"] == 40
    assert state["state"] == "entry_delay"
    assert state["entries_enabled"] is False
    clock[0] = 60
    assert gate.snapshot(healthy=True)["state"] == "hold_elapsed"
    assert gate.snapshot(healthy=False)["state"] == "blocked"
    gate.revoke()
    assert gate.snapshot(healthy=True)["state"] == "awaiting_validation"
