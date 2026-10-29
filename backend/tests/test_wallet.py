"""Exact-money, scoped storage, execution integration and reporting acceptance."""

import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

import pytest
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from test_option_planner import NOW, calendar, fixture
from test_paper_execution import drive, make_plan, opened, prices, ready

from alembic import command
from app.broker.paper_broker import PaperBroker
from app.db.models import (
    Base,
    DashboardAlert,
    PaperDailyPnL,
    PaperExecutionBook,
    PaperTradeSummary,
    WalletAccount,
    WalletLedger,
    WalletPeriod,
    WalletReconciliationRun,
)
from app.db.session import database_engine
from app.execution.models import FillSettings, PositionStatus, RiskSettings
from app.execution.service import PaperExecution
from app.wallet.contracts import MAX_MONEY, CostSchedule, WalletSettings
from app.wallet.projections import ReconciliationError
from app.wallet.reconciliation import WalletReconciler
from app.wallet.reporting import HistoryQuery
from app.wallet.service import WalletService

D = Decimal


@pytest.fixture
def wallet(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'wallet.db').as_posix()}")
    Base.metadata.create_all(engine)
    service = WalletService(
        engine,
        calendar(),
        FillSettings(latency_ms=0, fee_per_order=D("1.25")),
        RiskSettings(max_trade_loss_pct=D(20), max_trades=20),
        settings=WalletSettings(initial_capital=D(100000)),
    )
    service.initialize(NOW)
    yield service
    engine.dispose()


def close_trade(wallet, identity, plan, at=NOW, short="90", hedge="9"):
    wallet.close(identity, at)
    p = drive(wallet, plan, at, short=short, hedge=hedge)
    assert p.status == PositionStatus.CLOSED
    return p


def test_initialize_once_and_exact_scoped_tables(wallet):
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: wallet.initialize(NOW), range(2)))
    restored = WalletService(
        wallet.engine,
        wallet.calendar,
        wallet.fills,
        wallet.risk,
        settings=wallet.snapshot().wallet_settings,
    )
    restored.initialize(NOW)
    b = restored.snapshot()
    assert b.balance == D(100000) and len(b.ledger) == 1
    with Session(wallet.engine) as db:
        account = db.get(WalletAccount, "PAPER")
        assert account.user_id == "local" and account.mode == "PAPER"
        assert account.balance == "100000"
        assert len(db.scalars(select(WalletLedger)).all()) == 1
        assert db.scalars(select(WalletPeriod)).all()
    alice = WalletService(
        wallet.engine,
        calendar(),
        user_id="alice",
        settings=WalletSettings(initial_capital=D(50)),
    )
    alice.initialize(NOW)
    alice.deposit("same-key", D(10), NOW)
    wallet.deposit("same-key", D(20), NOW)
    assert alice.snapshot().balance == 60 and wallet.snapshot().balance == 100020
    assert alice.history()["items"] == []


@pytest.mark.parametrize(
    "amount",
    [D(0), D(-1), D(".001"), D("NaN"), D("Infinity"), MAX_MONEY + 1, 0.1, True],
)
def test_invalid_deposits_leave_storage_unchanged(wallet, amount):
    before = wallet.snapshot()
    with pytest.raises((ValueError, TypeError)):
        wallet.deposit("bad", amount, NOW)
    assert wallet.snapshot() == before


def test_precision_boundary_and_overflow(wallet):
    wallet.reset("max", MAX_MONEY, NOW)
    with pytest.raises(ValueError, match="precision"):
        wallet.deposit("overflow", D(".01"), NOW)
    assert wallet.snapshot().balance == MAX_MONEY
    wallet.withdraw("all", MAX_MONEY, NOW)
    assert wallet.snapshot().balance == 0


def test_withdraw_free_only_and_idempotent_retry(wallet):
    identity, plan = opened(wallet)
    free = wallet.capital(NOW).free_capital
    wallet.withdraw("free", free, NOW)
    assert wallet.snapshot().balance == wallet.snapshot().reserved
    wallet.withdraw("free", free, NOW)
    with pytest.raises(ValueError, match="conflict"):
        wallet.withdraw("free", D(1), NOW)
    with pytest.raises(ValueError, match="free balance"):
        wallet.withdraw("more", D(".01"), NOW)
    close_trade(wallet, identity, plan)
    assert wallet.snapshot().reserved == 0


def test_reset_preserves_history_and_risk_locks_and_requires_flat(wallet):
    identity, plan = opened(wallet)
    with pytest.raises(ValueError, match="cannot reset"):
        wallet.reset("blocked", D(1), NOW)
    close_trade(wallet, identity, plan)
    wallet.kill(NOW)
    before = wallet.snapshot()
    wallet.reset("baseline", D(50000), NOW)
    wallet.reset("baseline", D(50000), NOW)
    after = wallet.snapshot()
    assert after.balance == 50000 and after.killed
    assert after.positions == before.positions and after.day_trades == before.day_trades
    assert len(after.ledger) == len(before.ledger) + 1
    assert after.ledger[-1].amount == D(50000) - before.balance
    with pytest.raises(ValueError, match="conflict"):
        wallet.reset("baseline", D(50001), NOW)
    assert wallet.history()["items"][0]["net"] == "632.50"


@pytest.mark.parametrize("amount", [D(0), D(-1), D(".001"), D("NaN"), MAX_MONEY + 1])
def test_invalid_withdrawals(wallet, amount):
    with pytest.raises(ValueError):
        wallet.withdraw("invalid", amount, NOW)


def test_wallet_clock_regression_rejected(wallet):
    before = wallet.snapshot()
    with pytest.raises(ValueError, match="clock regression"):
        wallet.deposit("past", D(1), NOW - timedelta(seconds=1))
    assert wallet.snapshot() == before


def test_auto_topup_exact_shortfall_atomic_and_never_bypasses_risk(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'auto.db').as_posix()}")
    Base.metadata.create_all(engine)
    w = WalletService(
        engine,
        calendar(),
        FillSettings(latency_ms=0),
        RiskSettings(max_trade_loss_pct=D(20)),
        settings=WalletSettings(initial_capital=D(100000), auto_topup=True),
    )
    try:
        w.initialize(NOW)
        w.rollover(NOW)
        w.withdraw("reduce", D(95000), NOW)
        sig, cat, quotes, settings = fixture()
        from app.strategy.planner import build_plan

        plan = build_plan(
            sig, cat, quotes, w.planning_capital(NOW), NOW, calendar(), settings
        ).plan
        identity = w.enter("auto", plan, NOW, ready(), prices(plan))
        assert identity
        b = w.snapshot()
        topups = [e for e in b.ledger if e.key.startswith("auto:")]
        assert len(topups) == 1 and topups[0].amount == D("4116.25")
        assert b.balance == b.reserved == D("9116.25")
        assert w.enter("auto", plan, NOW, ready(), prices(plan)) == identity
        assert len([e for e in w.snapshot().ledger if e.key.startswith("auto:")]) == 1
        assert w.capital(NOW).free_capital == 0
        assert w.planning_capital(NOW).free_capital > 0  # explicit funding ceiling only
    finally:
        engine.dispose()


def test_topup_does_not_happen_for_rejected_risk(wallet):
    # Default disabled and no top-up on failed admission.
    plan = make_plan(wallet)
    wallet.withdraw("reduce", D(95000), NOW)
    assert wallet.enter("reject", plan, NOW, ready(feed=False), prices(plan)) is None
    assert not any(e.key.startswith("auto:") for e in wallet.snapshot().ledger)


def test_margin_and_pnl_projections_commit_together_and_rollback(wallet, monkeypatch):
    import app.execution.service as execution_module

    identity, plan = opened(wallet)
    with Session(wallet.engine) as db:
        assert D(db.get(WalletAccount, "PAPER").reserved) == plan.required_margin
    wallet.close(identity, NOW)
    drive(wallet, plan, count=4)
    before = wallet.snapshot()
    original = execution_module.synchronize

    def fail_after_projection(*args):
        original(*args)
        raise RuntimeError("projection failure")

    with monkeypatch.context() as patch:
        patch.setattr(execution_module, "synchronize", fail_after_projection)
        with pytest.raises(RuntimeError, match="projection failure"):
            wallet.step(NOW, prices(plan), ready())
    assert wallet.snapshot() == before
    p = drive(wallet, plan)
    assert p.status == PositionStatus.CLOSED
    with Session(wallet.engine) as db:
        account = db.get(WalletAccount, "PAPER")
        row = db.get(PaperTradeSummary, ("PAPER", identity))
        assert account.reserved == "0.00"
        assert json.loads(row.payload)["net"] == str(p.gross - p.costs)
        assert len(db.scalars(select(PaperTradeSummary)).all()) == 1


def synthetic_schedule(**kw):
    return CostSchedule(
        **(
            dict(
                identity="synthetic-v1",
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 12, 31),
                source="SYNTHETIC_NOT_BROKER_RATES",
                brokerage_per_order=D(2),
                exchange_pct=D(".1"),
                sebi_pct=D(".01"),
                ipft_pct=D(".02"),
                stt_sell_pct=D(".2"),
                stamp_buy_pct=D(".03"),
                gst_pct=D(10),
            )
            | kw
        )
    )


@pytest.mark.parametrize("side,expected", [("BUY", D("3.91")), ("SELL", D("5.61"))])
def test_cost_categories_independent_arithmetic(side, expected):
    schedule = synthetic_schedule()
    # turnover 1000: brokerage 2, exchange 1, SEBI .10, IPFT .20, GST .31.
    # Buy stamp .30, sell STT 2.00.
    parts = schedule.estimate(side, D(1000), NOW.date())
    assert parts["stt"] == (D(2) if side == "SELL" else 0)
    assert parts["stamp"] == (D(".30") if side == "BUY" else 0)
    assert sum(parts.values()) == expected


def test_detailed_costs_persist_to_fill_and_close(wallet):
    settings = FillSettings(latency_ms=0, cost_schedule=synthetic_schedule())
    broker = PaperBroker(settings)
    o = broker.place("costed", 1, "BUY", 100, D(".05"), NOW)
    from app.execution.models import MarketPrice

    quote = MarketPrice(
        token=1,
        at=NOW,
        received_at=NOW,
        last=D(10),
        bid=D(10),
        ask=D(10),
        bid_quantity=100,
        ask_quantity=100,
    )
    filled = broker.process(o, quote, NOW)
    assert filled.fill.cost_schedule_id == "synthetic-v1"
    assert filled.fill.costs == D("3.91")
    assert filled.fill.costs == sum(filled.fill.cost_parts.values())
    expired = synthetic_schedule(effective_to=NOW.date() - timedelta(days=1))
    rejected = PaperBroker(FillSettings(latency_ms=0, cost_schedule=expired)).process(
        o, quote, NOW
    )
    assert (
        rejected.status == "REJECTED" and rejected.reason == "cost_schedule_unavailable"
    )
    with pytest.raises(ValidationError):
        FillSettings(fee_per_order=D(1), cost_schedule=synthetic_schedule())


def test_period_returns_exclude_midperiod_deposits_withdrawals_reset(wallet):
    identity, plan = opened(wallet)
    close_trade(wallet, identity, plan)
    wallet.deposit("add", D(100000), NOW)
    wallet.withdraw("remove", D(50000), NOW)
    wallet.reset("reset", D(1000000), NOW)
    daily = wallet.period("daily", NOW)
    assert daily["starting_capital"] == "100000"
    assert daily["net"] == "632.50"
    assert daily["capital_return_pct"] == "0.632500"
    assert D(daily["by_family_net"]["CO"]) == D(daily["net"])
    trade = wallet.history()["items"][0]
    assert D(trade["margin_return_pct"]) == (D("632.50") / D("9116.25") * 100).quantize(
        D(".000001")
    )
    assert trade["capital_return_pct"] == "0.632500"
    assert wallet.period("all", NOW)["net"] == "632.50"


def test_period_boundaries_and_zero_denominator(wallet):
    identity, plan = opened(wallet)
    close_trade(wallet, identity, plan)
    wallet.deposit("nextday", D(1000), NOW + timedelta(days=1))
    next_day = wallet.period("daily", NOW + timedelta(days=1))
    assert next_day["starting_capital"] == "100632.50" and D(next_day["net"]) == 0
    assert next_day["capital_return_pct"] == "0.000000"
    next_month = wallet.period("monthly", NOW.replace(month=11, day=1))
    assert D(next_month["starting_capital"]) == D("101632.50")
    assert next_month["trades"] == 0
    weekly = wallet.period("weekly", NOW)
    assert weekly["start"] == "2026-10-26" and weekly["capital_return_pct"] is None
    assert D(weekly["net"]) == D("632.50")


def test_history_filters_cursor_detail_and_export_agree(wallet):
    for i in range(3):
        plan = make_plan(wallet, signal_id=f"s{i}")
        identity = wallet.enter(f"d{i}", plan, NOW, ready(), prices(plan))
        drive(wallet, plan, count=4)
        close_trade(wallet, identity, plan)
    query = HistoryQuery(
        limit=1,
        family="CO",
        direction=1,
        grade=3,
        result="WIN",
        start=NOW.date(),
        end=NOW.date(),
    )
    first = wallet.history(query)
    second = wallet.history(query.model_copy(update={"cursor": first["next_cursor"]}))
    third = wallet.history(query.model_copy(update={"cursor": second["next_cursor"]}))
    ids = [p["items"][0]["trade_id"] for p in (first, second, third)]
    assert len(set(ids)) == 3 and ids == sorted(ids) and third["next_cursor"] is None
    assert wallet.detail(ids[0])["status"] == "CLOSED"
    exported = list(csv.DictReader(io.StringIO(wallet.export_csv(query))))
    assert [r["trade_id"] for r in exported] == ids
    assert wallet.history(HistoryQuery(result="LOSS"))["items"] == []
    with pytest.raises(ValueError, match="cursor"):
        wallet.history(HistoryQuery(cursor="%%%"))
    with pytest.raises(ValueError, match="cursor"):
        wallet.history(
            query.model_copy(update={"family": "DIV", "cursor": first["next_cursor"]})
        )
    wallet.deposit("change", D(1), NOW)
    with pytest.raises(ValueError, match="cursor"):
        wallet.history(query.model_copy(update={"cursor": first["next_cursor"]}))


@pytest.mark.parametrize("sort", ["net", "closed_at"])
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_history_global_sort_cursor_export_and_readonly_display(wallet, sort, order):
    for i, price in enumerate(["85", "95", "90"]):
        plan = make_plan(wallet, signal_id=f"sorted{i}")
        identity = wallet.enter(f"sorted{i}", plan, NOW, ready(), prices(plan))
        drive(wallet, plan, count=4)
        close_trade(wallet, identity, plan, short=price)
    with Session(wallet.engine) as db:
        before = {r.trade_id: r.payload for r in db.scalars(select(PaperTradeSummary))}
    all_rows = wallet.history(HistoryQuery(limit=100))["items"]
    key = (
        (lambda r: (D(r["net"]), r["closed_at"], r["trade_id"]))
        if sort == "net"
        else (lambda r: (r["closed_at"], r["trade_id"]))
    )
    expected = sorted(all_rows, key=key, reverse=order == "desc")
    query = HistoryQuery(sort=sort, order=order, limit=1)
    records = []
    while True:
        page = wallet.history(query)
        records.extend(page["items"])
        if page["next_cursor"] is None:
            break
        query = query.model_copy(update={"cursor": page["next_cursor"]})
    assert [r["trade_id"] for r in records] == [r["trade_id"] for r in expected]
    assert len({r["trade_id"] for r in records}) == 3
    for row in records:
        p = wallet.snapshot().positions[row["trade_id"]]
        assert row["quantity"] == p.plan.short.quantity
        assert D(row["short_entry"]) == p.orders["entry_short"].fill.price
        assert D(row["short_exit"]) == p.orders["exit_short"].fill.price
        assert D(row["hedge_exit"]) == p.orders["exit_hedge"].fill.price
        assert row["duration_seconds"] == 0
    exported = list(
        csv.DictReader(
            io.StringIO(
                wallet.export_csv(HistoryQuery(sort=sort, order=order, limit=1))
            )
        )
    )
    assert [r["trade_id"] for r in exported] == [r["trade_id"] for r in records]
    with Session(wallet.engine) as db:
        assert {
            r.trade_id: r.payload for r in db.scalars(select(PaperTradeSummary))
        } == before
    first = wallet.history(HistoryQuery(sort=sort, order=order, limit=1))
    with pytest.raises(ValueError, match="cursor"):
        wallet.history(
            HistoryQuery(
                sort=sort,
                order="desc" if order == "asc" else "asc",
                limit=1,
                cursor=first["next_cursor"],
            )
        )


@pytest.mark.parametrize(
    "table",
    [WalletAccount, WalletLedger, PaperTradeSummary, PaperDailyPnL, WalletPeriod],
)
def test_projection_corruption_fails_closed_and_alerts(wallet, table):
    identity, plan = opened(wallet)
    close_trade(wallet, identity, plan)
    with Session(wallet.engine) as db, db.begin():
        row = db.scalars(select(table)).first()
        if table is WalletAccount:
            row.balance = "123"
        else:
            row.payload = "{}"
    with pytest.raises(ReconciliationError):
        wallet.deposit("blocked", D(1), NOW)
    result = WalletReconciler(wallet.engine).poll(NOW.replace(hour=16))
    assert result == {"PAPER": "FAIL"}
    with Session(wallet.engine) as db:
        alerts = db.scalars(select(DashboardAlert)).all()
        assert (
            len(alerts) >= 1 and alerts[0].code == "paper_wallet_reconciliation_failed"
        )
        from app.api.live_contracts import AlertData

        public = AlertData(
            id=alerts[0].id,
            level=alerts[0].level,
            code=alerts[0].code,
            at=alerts[0].at,
            acknowledged_at=alerts[0].acknowledged_at,
        )
        assert public.level == "critical"


def test_nightly_reconciliation_is_durable_and_does_not_mutate_wallet(wallet):
    before = wallet.snapshot()
    r = WalletReconciler(wallet.engine)
    assert r.poll(NOW) == {}
    evening = NOW.replace(hour=15, minute=35)
    assert r.poll(evening) == {"PAPER": "PASS"}
    assert WalletReconciler(wallet.engine).poll(evening) == {}
    assert wallet.snapshot() == before
    with Session(wallet.engine) as db:
        assert len(db.scalars(select(WalletReconciliationRun)).all()) == 1
        assert db.scalars(select(DashboardAlert)).all() == []


def test_legacy_book_bootstraps_projections_without_reinitializing(wallet):
    # Simulate a valid BE-11 book migrated before wallet projections existed.
    with Session(wallet.engine) as db, db.begin():
        row = db.get(PaperExecutionBook, "PAPER")
        payload = json.loads(row.payload)
        payload.pop("projected")
        row.payload = json.dumps(payload)
        for model in (WalletAccount, WalletLedger, PaperDailyPnL, WalletPeriod):
            for item in db.scalars(select(model)).all():
                db.delete(item)
    restored = PaperExecution(wallet.engine, wallet.calendar, wallet.fills, wallet.risk)
    assert restored.snapshot().balance == 100000
    assert len(restored.snapshot().ledger) == 1


def test_wallet_migration_is_additive_indexed_and_reversible(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0009_paper_execution")
    engine = database_engine(url)
    before = set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO paper_execution_books VALUES ('preserve',1,'{}')"
        )
    command.upgrade(config, "0010_wallet")
    assert set(inspect(engine).get_table_names()) - before == {
        "wallet_accounts",
        "wallet_ledger",
        "paper_trade_summaries",
        "paper_daily_pnl",
        "wallet_periods",
        "wallet_reconciliation_runs",
    }
    assert len(inspect(engine).get_indexes("paper_trade_summaries")) == 2
    command.downgrade(config, "0009_paper_execution")
    assert set(inspect(engine).get_table_names()) == before
    with engine.connect() as conn:
        assert (
            conn.exec_driver_sql(
                "SELECT payload FROM paper_execution_books WHERE id='preserve'"
            ).scalar_one()
            == "{}"
        )
    engine.dispose()


def test_scope_prevents_history_and_detail_leaks(wallet):
    identity, plan = opened(wallet)
    close_trade(wallet, identity, plan)
    alice = WalletService(wallet.engine, wallet.calendar, user_id="alice")
    assert alice.history()["items"] == []
    with pytest.raises(KeyError):
        alice.detail(identity)
    with pytest.raises(ValidationError):
        HistoryQuery(mode="LIVE")
    with pytest.raises(ValueError):
        WalletService(wallet.engine, wallet.calendar, user_id="../other")


def test_detailed_costs_flow_through_actual_two_leg_settlement(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'fees.db').as_posix()}")
    Base.metadata.create_all(engine)
    w = WalletService(
        engine,
        calendar(),
        FillSettings(latency_ms=0, cost_schedule=synthetic_schedule()),
        RiskSettings(max_trade_loss_pct=D(20)),
        settings=WalletSettings(initial_capital=D(100000)),
    )
    try:
        w.initialize(NOW)
        identity, plan = opened(w)
        position = close_trade(w, identity, plan)
        components = [o.fill.cost_parts for o in position.orders.values()]
        total = sum((sum(parts.values()) for parts in components), D(0))
        assert position.gross == D("637.50") and position.costs == total
        assert w.snapshot().balance == D(100000) + position.gross - total
        assert D(w.history()["items"][0]["costs"]) == total
    finally:
        engine.dispose()


def test_zero_wallet_initialization_and_reset_cannot_bypass_loss_lock(wallet):
    identity, plan = opened(wallet)
    wallet.step(NOW, prices(plan, short="140", hedge="10"), ready())
    drive(wallet, plan, short="140", hedge="10")
    assert wallet.snapshot().loss_locked
    wallet.reset("restore", D(100000), NOW)
    assert wallet.snapshot().loss_locked
    plan2 = make_plan(wallet, signal_id="after-reset")
    assert wallet.enter("after-reset", plan2, NOW, ready(), prices(plan2)) is None


def test_local_ui_readiness_never_mistakes_api_docs_or_empty_build_for_paper_ui(
    tmp_path,
):
    from app.tools.local_ui_readiness import readiness

    (tmp_path / "README.md").write_text("| BE-12-01 | Completed | test |\n")
    report = readiness(tmp_path)
    assert report["status"] == "BLOCKED" and not report["paper_trading_ready"]
    assert "FE-14-01" in report["pending"]["ui_shell_auth_controls"]
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    (tmp_path / "frontend" / "package.json").write_text("{}")
    (tmp_path / "frontend" / "dist" / "index.html").write_text("<html></html>")
    assert readiness(tmp_path)["status"] == "BLOCKED"


@pytest.mark.asyncio
async def test_nightly_job_uses_existing_owned_scheduler_only_when_enabled(
    wallet, tmp_path
):
    from unittest.mock import AsyncMock, Mock

    from app.config import Settings
    from app.market.service import MarketService

    settings = Settings(
        _env_file=None,
        market_service_enabled=True,
        wallet_reconciliation_enabled=True,
        market_lock_file=tmp_path / "owner.lock",
    )
    service = MarketService(
        settings, Mock(), wallet.engine, Mock(), clock=lambda: NOW.replace(hour=16)
    )
    service._step = AsyncMock()
    try:
        await service.step()
        with Session(wallet.engine) as db:
            assert len(db.scalars(select(WalletReconciliationRun)).all()) == 1
        settings.wallet_reconciliation_enabled = False
        service.wallet_reconciler.poll = Mock(side_effect=AssertionError("disabled"))
        await service.step()
    finally:
        service.lease.release()


def test_enabled_topup_still_cannot_fund_rejected_readiness(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'rejected.db').as_posix()}")
    Base.metadata.create_all(engine)
    w = WalletService(
        engine,
        calendar(),
        FillSettings(latency_ms=0),
        RiskSettings(max_trade_loss_pct=D(20)),
        settings=WalletSettings(initial_capital=D(100000), auto_topup=True),
    )
    try:
        w.initialize(NOW)
        w.rollover(NOW)
        w.withdraw("reduce", D(95000), NOW)
        sig, cat, quotes, settings = fixture()
        from app.strategy.planner import build_plan

        plan = build_plan(
            sig, cat, quotes, w.planning_capital(NOW), NOW, calendar(), settings
        ).plan
        assert w.enter("rejected", plan, NOW, ready(feed=False), prices(plan)) is None
        assert w.snapshot().balance == 5000 and w.snapshot().reserved == 0
        assert not any(e.key.startswith("auto:") for e in w.snapshot().ledger)
    finally:
        engine.dispose()


def test_csv_formula_symbols_are_escaped(wallet):
    plan = make_plan(wallet)
    contract = plan.short.contract.model_copy(update={"symbol": "=BAD()"})
    plan = plan.model_copy(
        update={"short": plan.short.model_copy(update={"contract": contract})}
    )
    identity = wallet.enter("formula", plan, NOW, ready(), prices(plan))
    assert identity
    drive(wallet, plan, count=4)
    close_trade(wallet, identity, plan)
    row = list(csv.DictReader(io.StringIO(wallet.export_csv())))[0]
    assert row["short_symbol"] == "'=BAD()"


@pytest.mark.parametrize("include_ipft,gst", [(False, D(".31")), (True, D(".33"))])
def test_gst_ipft_option_and_paise_half_up_rounding(include_ipft, gst):
    schedule = synthetic_schedule(gst_on_ipft=include_ipft)
    assert schedule.estimate("BUY", D(1000), NOW.date())["gst"] == gst
    assert schedule.estimate("BUY", D(5), NOW.date())["exchange"] == D(".01")
