"""Independent exact-money lifecycle drills, isolated from the managed feed."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect
from test_option_planner import NOW, calendar, fixture

from alembic import command
from app.broker.paper_broker import PaperBroker
from app.db.models import Base
from app.db.session import database_engine
from app.execution.models import (
    FillSettings,
    MarketPrice,
    Mode,
    PositionStatus,
    Readiness,
    RiskSettings,
)
from app.execution.service import PaperExecution
from app.market.warmup import Session, SessionCalendar
from app.strategy.models import StrategySettings
from app.strategy.planner import build_plan

D = Decimal


def ready(at=NOW, **kw):
    return Readiness(
        **(
            dict(
                at=at,
                feed=True,
                authenticated=True,
                recovered=True,
                indicators=True,
                clock=True,
                event_blocked=False,
            )
            | kw
        )
    )


def prices(plan, at=NOW, short="100", hedge="10.50", depth=10000):
    return {
        leg.contract.token: MarketPrice(
            token=leg.contract.token,
            at=at,
            received_at=at,
            last=D(value),
            bid=D(value),
            ask=D(value),
            bid_quantity=depth,
            ask_quantity=depth,
        )
        for leg, value in ((plan.short, short), (plan.hedge, hedge))
    }


def make_plan(service, at=NOW, signal_id="replay:1:0", settings=None):
    sig, cat, quotes, settings = fixture(settings=settings)
    sig = sig.model_copy(update={"signal_id": signal_id, "at": at})
    cat = cat.model_copy(update={"loaded_at": at - timedelta(hours=1)})
    quotes = {
        t: q.model_copy(update={"exchange_at": at, "received_at": at})
        for t, q in quotes.items()
    }
    result = build_plan(
        sig, cat, quotes, service.capital(at), at, service.calendar, settings
    )
    assert result.accepted, result.reason
    return result.plan


@pytest.fixture
def env(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'paper.db').as_posix()}")
    Base.metadata.create_all(engine)
    service = PaperExecution(
        engine,
        calendar(),
        FillSettings(latency_ms=0, fee_per_order=D("1.25")),
        RiskSettings(max_trade_loss_pct=D(20)),
    )
    service.deposit("initial", D(100000), NOW)
    yield service
    engine.dispose()


def drive(service, plan, at=NOW, count=8, **kw):
    for _ in range(count):
        service.step(at, prices(plan, at, **kw), ready(at))
    return next(iter(service.snapshot().positions.values()))


def opened(service, settings=None):
    plan = make_plan(service, settings=settings)
    identity = service.enter("decision", plan, NOW, ready(), prices(plan))
    assert identity
    p = drive(service, plan, count=4)
    assert p.status == PositionStatus.OPEN
    return identity, plan


@pytest.mark.parametrize("side,value", [("BUY", "10.55"), ("SELL", "9.95")])
def test_market_depth_tick_round_and_repeat(side, value):
    broker = PaperBroker(FillSettings(latency_ms=0))
    order = broker.place("test", 1, side, 75, D(".05"), NOW)
    price = MarketPrice(
        token=1,
        at=NOW,
        received_at=NOW,
        last=D("10.25"),
        bid=D("9.99"),
        ask=D("10.51"),
        bid_quantity=100,
        ask_quantity=100,
    )
    result = broker.process(order, price, NOW)
    assert result.id.startswith("P-") and result.fill.price == D(value)
    assert broker.process(result, price, NOW) == result
    assert broker.cancel(result) == result


@pytest.mark.parametrize("side,expected", [("BUY", "10.5"), ("SELL", "9.5")])
def test_fallback_slippage(side, expected):
    broker = PaperBroker(FillSettings(latency_ms=0))
    o = broker.place("fallback", 1, side, 1, D(".05"), NOW)
    p = MarketPrice(token=1, at=NOW, received_at=NOW, last=D(10))
    assert broker.process(o, p, NOW).fill.price == D(expected)


@pytest.mark.parametrize(
    "side,touch,miss", [("BUY", "9.95", "10.05"), ("SELL", "10.05", "9.95")]
)
def test_limit_touch_latency_and_cancellation(side, touch, miss):
    broker = PaperBroker(FillSettings())
    o = broker.place("limit", 1, side, 1, D(".05"), NOW, D(10))
    at = NOW + timedelta(milliseconds=500)
    price = MarketPrice(token=1, at=at, received_at=at, last=D(miss))
    assert broker.process(o, price, at).fill is None
    price = price.model_copy(update={"last": D(touch)})
    assert broker.process(o, price, NOW).fill is None
    assert broker.process(o, price, at).fill.at == at
    assert broker.process(o, price.model_copy(update={"at": NOW}), at).fill is None
    cancelled = broker.cancel(o)
    assert broker.process(cancelled, price, at) == cancelled


@pytest.mark.parametrize("bad", ["stale", "future", "token", "thin", "sanity"])
def test_market_bad_prices(bad):
    broker = PaperBroker(FillSettings(latency_ms=0, slippage=D(0)))
    o = broker.place("bad", 1, "BUY", 75, D(".05"), NOW)
    p = MarketPrice(
        token=1,
        at=NOW,
        received_at=NOW,
        last=D(10),
        bid=D(10),
        ask=D(10),
        bid_quantity=100,
        ask_quantity=100,
    )
    update = {
        "stale": {"at": NOW - timedelta(seconds=6)},
        "future": {"at": NOW + timedelta(seconds=1)},
        "token": {"token": 2},
        "thin": {"ask_quantity": 1},
        "sanity": {"ask": D(12)},
    }[bad]
    assert broker.process(o, p.model_copy(update=update), NOW).fill is None


def test_hedge_first_restart_short_first_close_and_exact_ledger(env):
    plan = make_plan(env)
    identity = env.enter("d1", plan, NOW, ready(), prices(plan))
    assert env.snapshot().reserved == D("9116.25")
    env.step(NOW, prices(plan), ready())
    p = env.snapshot().positions[identity]
    assert list(p.orders) == ["entry_hedge"]
    restored = PaperExecution(env.engine, env.calendar, env.fills, env.risk)
    p = drive(restored, plan, count=3)
    assert p.status == PositionStatus.OPEN
    assert p.orders["entry_hedge"].side == "BUY"
    assert p.orders["entry_short"].side == "SELL"
    restored.close(identity, NOW)
    restored.step(NOW, prices(plan, short="90", hedge="9"))
    p = restored.snapshot().positions[identity]
    assert "exit_short" in p.orders and "exit_hedge" not in p.orders
    p = drive(restored, plan, short="90", hedge="9")
    assert p.status == PositionStatus.CLOSED
    # (100 - 10.5 - 90 + 9) * 75 = 637.50; four fees of 1.25.
    assert p.gross == D("637.50") and p.costs == D("5.00")
    b = restored.snapshot()
    assert b.balance == D("100632.50") and b.reserved == 0
    assert len(b.ledger) == 5
    drive(restored, plan)
    assert restored.snapshot() == b


@pytest.mark.parametrize("failure", ["short_depth", "readiness", "cancel_before_fill"])
def test_partial_entry_unwinds_without_naked_short(env, failure):
    plan = make_plan(env)
    identity = env.enter("d1", plan, NOW, ready(), prices(plan))
    drive(env, plan, count=2)  # durable hedge fill only
    if failure == "short_depth":
        drive(env, plan, count=2, depth=1)
    elif failure == "readiness":
        env.step(NOW, prices(plan), ready(feed=False))
    else:
        env.close(identity, NOW)
    p = drive(env, plan)
    assert p.status == PositionStatus.CLOSED
    assert not env._filled(p, "entry_short")
    assert p.orders["exit_hedge"].side == "SELL"
    assert env.snapshot().reserved == 0
    assert env.snapshot().balance == D("99997.50")  # same-price unwind, two fees


def test_duplicate_signal_decision_deposit_and_concurrent_entry(env):
    plan = make_plan(env)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(
            pool.map(
                lambda _: env.enter("same", plan, NOW, ready(), prices(plan)), range(2)
            )
        )
    assert ids[0] == ids[1]
    assert env.enter("other", plan, NOW, ready(), prices(plan)) == ids[0]
    assert env.snapshot().day_trades == 1
    env.deposit("initial", D(100000), NOW)
    assert env.snapshot().balance == 100000
    with pytest.raises(ValueError, match="conflict"):
        env.deposit("initial", D(10), NOW)
    changed = make_plan(env, signal_id="different")
    with pytest.raises(ValueError, match="conflict"):
        env.enter("same", changed, NOW, ready(), prices(changed))


@pytest.mark.parametrize(
    "field",
    ["feed", "authenticated", "recovered", "clock", "indicators", "event_blocked"],
)
def test_final_readiness_rejects_are_durable(env, field):
    plan = make_plan(env)
    gate = ready(**{field: field == "event_blocked"})
    assert env.enter("rejected", plan, NOW, gate, prices(plan)) is None
    assert "readiness_or_event_block" in env.snapshot().rejects["rejected"].reasons
    assert env.enter("retry", plan, NOW, ready(), prices(plan)) is None
    assert env.snapshot().reserved == 0


@pytest.mark.parametrize(
    "case,reason",
    [
        ("stale", "stale_plan"),
        ("capital", "capital_unavailable_or_changed"),
        ("loss", "max_trade_loss"),
        ("window", "entry_window"),
        ("quote", "quote_quality_or_price_sanity"),
    ],
)
def test_final_risk_gate(env, case, reason):
    plan = make_plan(env)
    at = NOW
    market = prices(plan)
    if case == "stale":
        at += timedelta(seconds=6)
        market = prices(plan, at)
    elif case == "capital":
        env.deposit("topup", D(1), NOW)
    elif case == "loss":
        # A stricter service cannot silently replace persisted settings.
        env._mutate(lambda b, r: env._set(b, day=NOW.date(), day_capital=D(1)))
        plan = make_plan(env)
    elif case == "window":
        at = NOW.replace(hour=15)
        market = prices(plan, at)
    else:
        market = {}
    assert env.enter("reject", plan, at, ready(at), market) is None
    assert reason in env.snapshot().rejects["reject"].reasons


@pytest.mark.parametrize(
    "exit_kind", ["manual", "indicator", "square_off", "kill", "stop", "target"]
)
def test_all_exit_sources_and_stale_exit_wait(env, exit_kind, tmp_path):
    settings = StrategySettings(profit_capture_enabled=exit_kind == "target")
    identity, plan = opened(env, settings)
    at = NOW
    short, hedge = "100", "10.50"
    if exit_kind == "manual":
        env.close(identity, at)
    elif exit_kind == "indicator":
        env.indicator_exit(plan.signal.trade_id, at)
    elif exit_kind == "square_off":
        at = NOW.replace(hour=15, minute=15)
    elif exit_kind == "kill":
        flag = tmp_path / "KILL"
        flag.touch()
        assert env.poll_kill(flag, at)
    elif exit_kind == "stop":
        short = "180"
    else:
        short = "20"
    env.step(at, {}, ready(at))
    assert env.snapshot().reserved > 0
    p = drive(env, plan, at, short=short, hedge=hedge, count=10)
    assert p.status == PositionStatus.CLOSED
    assert p.exit_reason == {"stop": "premium_stop", "target": "premium_target"}.get(
        exit_kind, exit_kind
    )
    assert env.snapshot().reserved == 0


def test_stale_marks_are_unknown_and_daily_loss_lock_survives_restart(env):
    identity, plan = opened(env)
    env.step(NOW, {}, ready())
    assert env.snapshot().positions[identity].unrealised is None
    # 40.5 points * 75 plus costs breaches 2% daily capital.
    env.step(NOW, prices(plan, short="140", hedge="10"), ready())
    assert env.snapshot().loss_locked
    p = drive(env, plan, short="140", hedge="10")
    assert p.status == PositionStatus.CLOSED and p.exit_reason == "daily_loss"
    restored = PaperExecution(env.engine, env.calendar, env.fills, env.risk)
    assert restored.snapshot().loss_locked
    plan2 = make_plan(restored, signal_id="second")
    assert restored.enter("second", plan2, NOW, ready(), prices(plan2)) is None
    assert "daily_loss_locked" in restored.snapshot().rejects["second"].reasons


def test_valid_rollover_only_and_kill_persists(env):
    env.rollover(NOW)
    env.kill(NOW)
    tomorrow = NOW + timedelta(days=1)
    with pytest.raises(ValueError):
        env.rollover(tomorrow)
    cal = SessionCalendar(
        NOW.date(),
        tomorrow.date(),
        (
            Session(NOW.replace(hour=9, minute=15), NOW.replace(hour=15, minute=30)),
            Session(
                tomorrow.replace(hour=9, minute=15),
                tomorrow.replace(hour=15, minute=30),
            ),
        ),
    )
    restored = PaperExecution(env.engine, cal, env.fills, env.risk)
    restored._mutate(lambda b, r: restored._set(b, loss_locked=True, day_trades=3))
    restored.rollover(tomorrow)
    b = restored.snapshot()
    assert b.day_trades == 0 and not b.loss_locked and b.killed
    with pytest.raises(ValueError):
        restored.rollover(NOW)


def test_exit_depth_retries_retain_attempt_and_margin(env):
    identity, plan = opened(env)
    env.close(identity, NOW)
    drive(env, plan, count=3, depth=0)
    p = env.snapshot().positions[identity]
    assert p.status == PositionStatus.CLOSING and env.snapshot().reserved > 0
    assert any(":attempt:" in key for key in p.orders)
    p = drive(env, plan)
    assert p.status == PositionStatus.CLOSED
    assert len({o.id for o in p.orders.values()}) == len(p.orders)


def test_settings_cannot_change_on_restart_and_live_never_arms(env):
    with pytest.raises(ValueError, match="settings differ"):
        PaperExecution(env.engine, env.calendar)
    for kw in ({"mode": "LIVE"}, {"armed": True}):
        with pytest.raises(ValidationError):
            Mode(**kw)


@pytest.mark.parametrize("crash_step", range(10))
def test_restart_at_each_entry_and_exit_commit_matches_uninterrupted(
    tmp_path, crash_step
):
    outputs = []
    for run in range(2):
        engine = database_engine(f"sqlite:///{(tmp_path / f'{run}.db').as_posix()}")
        Base.metadata.create_all(engine)
        s = PaperExecution(
            engine,
            calendar(),
            FillSettings(latency_ms=0),
            RiskSettings(max_trade_loss_pct=D(20)),
        )
        s.deposit("initial", D(100000), NOW)
        plan = make_plan(s)
        identity = s.enter("same", plan, NOW, ready(), prices(plan))
        for step in range(10):
            if run and step == crash_step:
                s = PaperExecution(engine, calendar(), s.fills, s.risk)
            if step == 4:
                s.close(identity, NOW)
            s.step(NOW, prices(plan), ready())
        assert s.snapshot().positions[identity].status == PositionStatus.CLOSED
        outputs.append(s.snapshot().model_dump_json())
        engine.dispose()
    assert outputs[0] == outputs[1]


def test_transaction_rollback_retains_position_margin_and_ledger(env, monkeypatch):
    identity, plan = opened(env)
    env.close(identity, NOW)
    drive(env, plan, count=4)
    before = env.snapshot()
    assert before.positions[identity].status == PositionStatus.CLOSING

    def fail(*args):
        raise RuntimeError("simulated storage failure")

    with monkeypatch.context() as patch:
        patch.setattr(env, "_ledger", fail)
        with pytest.raises(RuntimeError, match="storage failure"):
            env.step(NOW, prices(plan), ready())
    assert env.snapshot() == before
    p = drive(env, plan)
    assert p.status == PositionStatus.CLOSED and env.snapshot().reserved == 0


def test_persistent_flag_does_not_cancel_exit_repeatedly(env, tmp_path):
    identity, plan = opened(env)
    flag = tmp_path / "KILL"
    flag.touch()
    for _ in range(8):
        env.step(NOW, prices(plan), ready(), kill_flag=flag)
    assert env.snapshot().positions[identity].status == PositionStatus.CLOSED
    new_plan = make_plan(env, signal_id="second")
    assert env.enter("new", new_plan, NOW, ready(), prices(new_plan)) is None
    assert "kill_locked" in env.snapshot().rejects["new"].reasons


def test_one_position_max_trades_and_open_session_rollover(env):
    identity, plan = opened(env)
    second = make_plan(env, signal_id="second")
    assert env.enter("second", second, NOW, ready(), prices(second)) is None
    assert "one_position" in env.snapshot().rejects["second"].reasons
    env.close(identity, NOW)
    drive(env, plan)
    env._mutate(lambda b, r: env._set(b, day_trades=env.risk.max_trades))
    third = make_plan(env, signal_id="third")
    assert env.enter("third", third, NOW, ready(), prices(third)) is None
    assert "max_trades" in env.snapshot().rejects["third"].reasons


def test_preview_capital_never_executes_and_book_corruption_fails_closed(env):
    from sqlalchemy.orm import Session as DBSession

    from app.db.models import PaperExecutionBook

    plan = make_plan(env)
    capital = plan.capital.model_copy(update={"source": "USER_PREVIEW"})
    preview_plan = plan.model_copy(update={"capital": capital})
    assert env.enter("preview", preview_plan, NOW, ready(), prices(plan)) is None
    with DBSession(env.engine) as db, db.begin():
        row = db.get(PaperExecutionBook, "PAPER")
        import json

        payload = json.loads(row.payload)
        payload["balance"] = "999999"
        row.payload = json.dumps(payload)
    with pytest.raises(ValidationError, match="reconciliation"):
        env.snapshot()


def test_clock_regression_skew_and_wrong_token_marks(env):
    identity, plan = opened(env)
    with pytest.raises(ValueError, match="clock regression"):
        env.step(NOW - timedelta(seconds=1), prices(plan), ready())
    for bad in ("skew", "token"):
        quotes = prices(plan)
        token = plan.short.contract.token
        quotes[token] = quotes[token].model_copy(
            update={"at": NOW - timedelta(seconds=3)} if bad == "skew" else {"token": 1}
        )
        env.step(NOW, quotes, ready())
        assert env.snapshot().positions[identity].unrealised is None


def test_api_kill_auth_csrf_audit_and_disabled_default(env):
    from auth_helpers import authenticate, password_hash
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    app = create_app(
        Settings(
            _env_file=None,
            database_url=str(env.engine.url),
            dashboard_password_hash=password_hash(),
        )
    )
    client = TestClient(app)
    try:
        assert client.post("/api/kill", json={}).status_code == 401
        authenticate(client)
        assert client.post("/api/kill", json={}).status_code == 409
        identity, plan = opened(env)
        app.state.paper_execution = env  # isolated owner attachment only
        csrf = client.headers.pop("X-CSRF-Token")
        assert client.post("/api/kill", json={}).status_code == 403
        client.headers["X-CSRF-Token"] = csrf
        response = client.post("/api/kill", json={})
        assert response.status_code == 200, response.text
        assert response.json()["entries_locked"]
        assert response.json()["pending_closures"] == 1
        assert env.snapshot().killed
        assert client.post("/api/kill", json={}).status_code == 200
    finally:
        app.state.market_service.auth.close()
        app.state.database_engine.dispose()


def test_migration_upgrade_downgrade_preserves_existing_tables(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0008_strategy")
    engine = database_engine(url)
    before = set(inspect(engine).get_table_names())
    command.upgrade(config, "0009_paper_execution")
    assert set(inspect(engine).get_table_names()) - before == {"paper_execution_books"}
    command.downgrade(config, "0008_strategy")
    assert set(inspect(engine).get_table_names()) == before
    engine.dispose()
