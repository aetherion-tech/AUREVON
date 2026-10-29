"""Persisted domain/API integration with synthetic data, providers and funds."""

import csv
import io
import json
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal

import pytest
from alembic.config import Config
from auth_helpers import authenticate, password_hash
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from test_option_planner import NOW, calendar, catalog, quote

from alembic import command
from app.api.domain_contracts import SettingsBundle, SettingsUpdate
from app.api.domain_service import PaperRuntime
from app.config import Settings
from app.db.models import (
    AuditEntry,
    Base,
    DomainDecision,
    IndicatorResult,
    MarketCheckpoint,
    StoredBrick,
)
from app.db.session import database_engine
from app.execution.models import (
    FillSettings,
    MarketPrice,
    PositionStatus,
    Readiness,
    RiskSettings,
)
from app.indicator.chart_history import publish_chart_history
from app.indicator.persistence import IndicatorRepository
from app.indicator.settings import IndicatorSettings
from app.main import create_app
from app.market.persistence import encode
from app.market.renko_builder import Brick
from app.strategy.models import StrategySettings
from app.wallet.contracts import WalletSettings
from app.wallet.service import WalletService

D = Decimal


@pytest.fixture
def domain(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{(tmp_path / 'domain.db').as_posix()}",
            dashboard_password_hash=password_hash(),
            market_stream="api-test",
            renko_anchor=23900,
        )
    )
    engine = app.state.database_engine
    Base.metadata.create_all(engine)
    pine = IndicatorSettings(atrLen=2, rsiLen=2, minGrade="Weak and above (all)")
    repo = IndicatorRepository(engine, "api-test", pine)
    series = [23900, 23950, 24000, 24050, 24000, 23950, 23900, 23850] * 5
    bricks = []
    for i in range(len(series) - 1):
        b = Brick(
            i,
            D(series[i]),
            D(series[i + 1]),
            1 if series[i + 1] > series[i] else -1,
            NOW.replace(hour=9, minute=30) + timedelta(minutes=i),
        )
        result = repo.process(b)
        bricks.append(b)
        entries = [j for j, e in enumerate(result["events"]) if e["kind"] == "ENTRY"]
        if entries:
            ordinal = entries[0]
            sd = result["events"][ordinal]["direction"]
            break
    else:
        pytest.fail("synthetic indicator fixture must emit a real ENTRY")
    with Session(engine) as db, db.begin():
        db.add(
            MarketCheckpoint(
                stream="api-test",
                revision=1,
                state="{}",
                configuration=encode(
                    dict(
                        spot=111,
                        future=222,
                        box="50",
                        anchor="23900",
                        mode="minute_close",
                    )
                ),
            )
        )
        for b in bricks:
            db.add(
                StoredBrick(stream="api-test", index=b.index, payload=encode(asdict(b)))
            )
    publish_chart_history(engine, "api-test")
    wall = [bricks[-1].ts]
    app.state.market_service.clock = lambda: wall[0]
    wallet = WalletService(
        engine,
        calendar(),
        FillSettings(latency_ms=0, fee_per_order=D("1.25")),
        RiskSettings(max_trade_loss_pct=D(20), max_trades=20),
        settings=WalletSettings(initial_capital=D(100000)),
    )
    wallet.initialize(wall[0])
    app.state.paper_execution = wallet
    service = app.state.domain_service
    bundle = service.settings.defaults.model_copy(
        update=dict(
            pine=pine.values,
            fills=wallet.fills,
            risk=wallet.risk,
            wallet=wallet.snapshot().wallet_settings,
            strategy=StrategySettings(
                min_grade=1, skip_high_risk=False, skip_opposite_bias=False
            ),
        )
    )
    chosen = service.settings.update(
        SettingsUpdate(expected_revision=0, settings=bundle, rebuild=True)
    )
    cat = catalog()
    short_strike = D(24000) - sd * 50
    options = {
        c.token: quote(
            c,
            "100" if c.strike == short_strike else "10",
            "100.50" if c.strike == short_strike else "10.50",
        )
        for c in cat.contracts
    }

    def option_prices():
        return {
            t: q.model_copy(update={"exchange_at": wall[0], "received_at": wall[0]})
            for t, q in options.items()
        }

    def prices():
        return {
            t: MarketPrice(
                token=t,
                at=wall[0],
                received_at=wall[0],
                last=(q.bids[0].price + q.asks[0].price) / 2,
                bid=q.bids[0].price,
                ask=q.asks[0].price,
                bid_quantity=10000,
                ask_quantity=10000,
            )
            for t, q in options.items()
        }

    runtime = PaperRuntime(
        wallet,
        chosen,
        lambda at: Readiness(
            at=at,
            feed=True,
            authenticated=True,
            recovered=True,
            indicators=True,
            clock=True,
            event_blocked=False,
        ),
        lambda: cat,
        option_prices,
        prices,
        entries_allowed=True,
    )
    app.state.paper_runtime = runtime
    client = TestClient(app, base_url="https://testserver")
    authenticate(client)
    yield dict(
        client=client,
        app=app,
        wallet=wallet,
        service=service,
        runtime=runtime,
        wall=wall,
        index=bricks[-1].index,
        ordinal=ordinal,
    )
    engine.dispose()
    app.state.market_service.auth.close()


def post(d, path, body=None, key="action"):
    return d["client"].post(
        path, json={} if body is None else body, headers={"Idempotency-Key": key}
    )


def prepared(d, key="prepare"):
    r = post(
        d,
        "/api/decisions/prepare",
        dict(stream="api-test", index=d["index"], event_ordinal=d["ordinal"]),
        key,
    )
    assert r.status_code == 200, r.text
    assert r.json()["accepted"], r.text
    return r.json()["decision_id"]


def admitted(d):
    identity = prepared(d)
    r = post(d, f"/api/decisions/{identity}/confirm", key="confirm")
    assert r.status_code == 200 and r.json()["accepted"], r.text
    for _ in range(4):
        d["service"].poll(d["wall"][0])
    assert (
        d["wallet"].snapshot().positions[r.json()["trade_id"]].status
        == PositionStatus.OPEN
    )
    return identity, r.json()["trade_id"]


def test_live_display_plan_risk_and_final_close_projections(domain):
    from app.api.domain_service import wallet_view

    _, identity = admitted(domain)
    wallet = domain["wallet"]
    book = wallet.snapshot()
    position = book.positions[identity]
    view = domain["client"].get(f"/api/trades/{identity}").json()
    assert D(view["stop_debit_per_unit"]) == position.plan.stop_debit_per_unit
    assert D(view["profit_capture_debit_per_unit"]) == (
        position.plan.profit_capture_debit_per_unit
    )
    assert view["profit_capture_enabled"] == position.plan.profit_capture_enabled
    assert view["closed_at"] is None
    assert D(view["margin_return_pct"]) == (
        position.unrealised / position.plan.required_margin * 100
    )
    risk = wallet_view(wallet, book)
    limit = book.day_capital * wallet.risk.daily_loss_pct / 100
    assert risk.risk_day == book.day
    assert risk.daily_loss_limit == limit
    expected_used = max(D(0), -(book.day_net + position.unrealised - position.costs))
    assert risk.daily_loss_used == expected_used
    assert risk.daily_loss_utilisation_pct == expected_used / limit * 100
    response = post(domain, f"/api/trades/{identity}/close", key="live-close")
    assert response.status_code == 200
    for _ in range(6):
        domain["service"].poll(domain["wall"][0])
    final = domain["client"].get(f"/api/trades/{identity}").json()
    assert final["state"] == "CLOSED"
    assert final["exit_reason"] == "manual"
    assert final["closed_at"] is not None
    assert D(final["margin_return_pct"]) == (
        (D(final["gross"]) - D(final["costs"])) / D(final["margin"]) * 100
    )


def test_live_loss_projection_preserves_unknown_open_marks(domain):
    from app.api.domain_service import wallet_view

    _, identity = admitted(domain)
    wallet = domain["wallet"]
    book = wallet.snapshot()
    original = book.positions[identity]
    book.positions[identity] = original.model_copy(update={"unrealised": None})
    risk = wallet_view(wallet, book)
    assert risk.daily_loss_limit is not None
    assert risk.daily_loss_used is None
    assert risk.daily_loss_utilisation_pct is None
    assert wallet.snapshot().positions[identity].unrealised == original.unrealised


def test_history_http_integer_filters_and_export_keep_internal_validation(domain):
    from pydantic import ValidationError

    from app.wallet.reporting import HistoryQuery

    client = domain["client"]
    for path in ("/api/trades", "/api/trades/export"):
        assert client.get(path + "?limit=1&grade=1").status_code == 200
        assert client.get(path + "?limit=1&direction=1").status_code == 200
        assert client.get(path + "?limit=1&direction=-1").status_code == 200
        assert client.get(path + "?direction=0").status_code == 422
        assert client.get(path + "?direction=1.5").status_code == 422
        assert client.get(path + "?limit=1.5").status_code == 422
        assert client.get(path + "?limit=0").status_code == 422
    with pytest.raises(ValidationError):
        HistoryQuery(limit="1")


def test_history_period_extremes_and_trade_lineage_are_readonly(domain):
    _, identity = admitted(domain)
    c = domain["client"]
    detail = c.get(f"/api/trades/{identity}").json()
    assert detail["signal_stream"] == "api-test"
    assert detail["signal_index"] == domain["index"]
    assert detail["signal_explanation"]
    assert detail["orders"][0]["created_at"]
    assert detail["orders"][0]["eligible_at"]
    assert (
        post(domain, f"/api/trades/{identity}/close", key="history-close").status_code
        == 200
    )
    for _ in range(6):
        domain["service"].poll(domain["wall"][0])
    before = domain["wallet"].snapshot()
    row = c.get("/api/trades?sort=net&order=desc&limit=1").json()["items"][0]
    report = c.get("/api/pnl/summary?period=all").json()
    assert report["best_trade_id"] == report["worst_trade_id"] == identity
    assert D(report["best_trade_net"]) == D(row["net"])
    assert report["best_trade_net"] == report["worst_trade_net"]
    assert row["created_at"] == detail["created_at"]
    assert row["signal_id"] == before.positions[identity].plan.signal.signal_id
    assert domain["wallet"].snapshot() == before


def test_empty_period_extremes_remain_unavailable(domain):
    report = domain["client"].get("/api/pnl/summary?period=all").json()
    assert report["trades"] == 0
    assert report["best_trade_id"] is None and report["best_trade_net"] is None
    assert report["worst_trade_id"] is None and report["worst_trade_net"] is None


@pytest.mark.parametrize(
    "path",
    [
        "/api/wallet",
        "/api/wallet/ledger",
        "/api/positions/open",
        "/api/trades",
        "/api/pnl/summary",
        "/api/pnl/daily",
        "/api/pnl/periods",
        "/api/pnl/by-family",
        "/api/settings",
        "/api/settings/defaults",
        "/api/settings/export",
        "/api/decisions",
        "/api/signals?stream=api-test",
    ],
)
def test_domain_reads_require_dashboard_auth(domain, path):
    anonymous = TestClient(domain["app"], base_url="https://testserver")
    assert anonymous.get(path).status_code == 401


def test_signals_and_persisted_preview_admission_decisions_have_real_explanations(
    domain,
):
    c = domain["client"]
    response = c.get("/api/signals?stream=api-test&limit=1")
    assert response.status_code == 200, response.text
    signal = response.json()["items"][0]
    assert signal["explanation"] and signal["reason"]
    assert signal["mode"] == "INDICATOR_REPLAY"
    assert c.get("/api/signals?stream=missing").status_code == 404
    identity, trade = admitted(domain)
    decisions = c.get("/api/decisions?limit=1").json()
    assert decisions["pagination"]["next_offset"] == 1
    details = c.get(f"/api/decisions/{identity}").json()
    assert details["kind"] == "PREVIEW" and not details["executable"]
    assert any(
        x["kind"] == "PAPER_ADMISSION" for x in c.get("/api/decisions").json()["items"]
    )


def test_wallet_exact_mutations_csrf_idempotency_conflicts_and_reset(domain):
    c, w = domain["client"], domain["wallet"]
    assert c.post("/api/wallet/deposit", json={"amount": "1.00"}).status_code == 422
    csrf = c.headers.pop("X-CSRF-Token")
    assert post(domain, "/api/wallet/deposit", {"amount": "1.00"}).status_code == 403
    c.headers["X-CSRF-Token"] = csrf
    first = post(domain, "/api/wallet/deposit", {"amount": "50.00"}, "deposit")
    assert first.status_code == 200, first.text
    assert first.json()["balance"] == "100050.00"
    assert (
        post(domain, "/api/wallet/deposit", {"amount": "50.00"}, "deposit").json()
        == first.json()
    )
    assert (
        post(domain, "/api/wallet/deposit", {"amount": "51.00"}, "deposit").status_code
        == 409
    )
    assert (
        post(domain, "/api/wallet/withdraw", {"amount": "20.00"}, "withdraw").json()[
            "free"
        ]
        == "100030.00"
    )
    assert (
        post(
            domain,
            "/api/wallet/reset",
            {"amount": "100000.00", "confirm": "wrong"},
            "reset",
        ).status_code
        == 422
    )
    assert (
        post(
            domain,
            "/api/wallet/reset",
            {"amount": "100000.00", "confirm": "RESET PAPER WALLET"},
            "reset",
        ).status_code
        == 200
    )
    ledger = c.get("/api/wallet/ledger?limit=2").json()
    assert [r["sequence"] for r in ledger["items"]] == [0, 1]
    assert ledger["pagination"]["next_offset"] == 2
    assert c.get("/api/wallet?mode=LIVE").status_code == 422
    with Session(w.engine) as db:
        assert db.scalars(
            select(AuditEntry).where(AuditEntry.action == "POST /api/wallet/deposit")
        ).all()


@pytest.mark.parametrize("amount", ["0", "-1", "0.001", "NaN", "1000000000000.00", 1.1])
def test_bad_money_never_changes_wallet(domain, amount):
    before = domain["wallet"].snapshot()
    assert post(domain, "/api/wallet/deposit", {"amount": amount}).status_code == 422
    assert domain["wallet"].snapshot() == before


def test_prepare_confirm_fill_close_history_pnl_and_ledger_agree(domain):
    identity, trade = admitted(domain)
    c, w = domain["client"], domain["wallet"]
    positions = c.get("/api/positions/open").json()
    assert positions[0]["trade_id"] == trade and len(positions[0]["legs"]) == 2
    assert len(positions[0]["orders"]) == 2
    assert (
        post(domain, f"/api/decisions/{identity}/confirm", key="confirm").json()[
            "trade_id"
        ]
        == trade
    )
    assert w.snapshot().day_trades == 1
    assert (
        post(
            domain,
            "/api/wallet/reset",
            {"amount": "1.00", "confirm": "RESET PAPER WALLET"},
            "reset-open",
        ).status_code
        == 409
    )
    assert post(domain, "/api/market/service/stop", key="stop-open").status_code == 409
    r = post(domain, f"/api/trades/{trade}/close", key="close")
    assert r.status_code == 200 and r.json()["pending_closures"] == 1
    assert post(domain, f"/api/trades/{trade}/close", key="close").json() == r.json()
    for _ in range(6):
        domain["service"].poll(domain["wall"][0])
    assert c.get("/api/positions/open").json() == []
    detail = c.get(f"/api/trades/{trade}").json()
    assert detail["state"] == "CLOSED" and detail["exit_reason"] == "manual"
    history = c.get("/api/trades?family=OT&result=LOSS").json()
    assert len(history["items"]) == 1
    export = c.get("/api/trades/export?family=OT&result=LOSS")
    assert export.status_code == 200 and export.headers["content-type"].startswith(
        "text/csv"
    )
    assert list(csv.DictReader(io.StringIO(export.text)))[0]["trade_id"] == trade
    pnl = c.get("/api/pnl/summary?period=daily").json()
    assert pnl["net"] == detail["net"] == history["items"][0]["net"]
    assert D(c.get("/api/wallet").json()["balance"]) == D(100000) + D(pnl["net"])
    day = domain["wall"][0].date().isoformat()
    daily = c.get(f"/api/pnl/daily?start={day}&end={day}").json()
    families = c.get(f"/api/pnl/by-family?start={day}&end={day}").json()
    assert (
        daily[0]["net"] == pnl["net"] and families["by_family_net"]["OT"] == pnl["net"]
    )
    assert c.get("/api/pnl/periods?count=2").status_code == 200


def test_confirmation_rechecks_readiness_and_persists_reject_alert(domain):
    identity = prepared(domain)
    domain["runtime"].readiness = lambda at: Readiness(at=at)
    r = post(domain, f"/api/decisions/{identity}/confirm", key="bad-feed")
    assert r.status_code == 200 and not r.json()["accepted"], r.text
    assert "readiness" in r.json()["reason"]
    assert domain["wallet"].snapshot().reserved == 0
    decisions = domain["client"].get("/api/decisions").json()["items"]
    assert any(d["kind"] == "RISK_REJECT" and not d["accepted"] for d in decisions)
    assert any(
        a["code"] == "risk_reject"
        for a in domain["client"].get("/api/alerts").json()["items"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "not_authorized",
        "stale_source",
        "missing_signal",
        "changed_settings",
        "stale_clock",
    ],
)
def test_confirmation_fails_closed_on_missing_or_changed_server_evidence(domain, fault):
    identity = prepared(domain)
    if fault == "not_authorized":
        domain["runtime"].entries_allowed = False
    elif fault == "stale_source":
        with Session(domain["wallet"].engine) as db, db.begin():
            db.get(MarketCheckpoint, "api-test").revision += 1
    elif fault == "missing_signal":
        with Session(domain["wallet"].engine) as db, db.begin():
            db.delete(db.get(IndicatorResult, ("api-test", domain["index"])))
    elif fault == "changed_settings":
        old = domain["service"].settings.read()
        domain["service"].settings.update(
            SettingsUpdate(expected_revision=old.revision, settings=old.settings)
        )
    else:
        domain["wall"][0] += timedelta(seconds=10)
    r = post(domain, f"/api/decisions/{identity}/confirm", key="deny")
    assert r.status_code == 409 or (
        r.status_code == 200 and not r.json()["accepted"]
    ), r.text
    assert not domain["wallet"].snapshot().positions


def test_settings_version_roundtrip_rebuild_requirement_and_active_exposure_block(
    domain,
):
    c, s = domain["client"], domain["service"]
    original = c.get("/api/settings").json()
    bundle = original["settings"]
    bundle["data"]["box"] = "25"
    bundle["pine"]["boxSize"] = 25.0
    body = dict(expected_revision=original["revision"], settings=bundle, rebuild=False)
    assert (
        c.put(
            "/api/settings", json=body, headers={"Idempotency-Key": "grid-no"}
        ).status_code
        == 409
    )
    body["rebuild"] = True
    first = c.put("/api/settings", json=body, headers={"Idempotency-Key": "grid-yes"})
    assert first.status_code == 200, first.text
    assert first.json()["requires_rebuild"]
    assert (
        c.put(
            "/api/settings", json=body, headers={"Idempotency-Key": "grid-yes"}
        ).json()
        == first.json()
    )
    assert (
        c.put(
            "/api/settings", json=body, headers={"Idempotency-Key": "stale-grid"}
        ).status_code
        == 409
    )
    assert c.get("/api/settings/export").json() == first.json()["settings"]
    with pytest.raises(ValueError):
        s.rebind_wallet()
    with pytest.raises(ValueError):
        s.rebind_wallet("api-test")
    assert domain["wallet"].snapshot().balance == 100000
    assert "kite_api_key" not in first.text and "password" not in first.text


def test_risk_settings_owner_rebind_preserves_cash_history_and_locks(domain):
    s, w = domain["service"], domain["wallet"]
    old = s.settings.read()
    new = old.settings.model_copy(
        update={"risk": old.settings.risk.model_copy(update={"max_trades": 5})}
    )
    chosen = s.settings.update(
        SettingsUpdate(expected_revision=old.revision, settings=new)
    )
    before = w.snapshot()
    assert s.rebind_wallet() is w
    assert w.risk.max_trades == 5 and w.snapshot().ledger == before.ledger
    domain["app"].state.paper_runtime = PaperRuntime(
        w,
        chosen,
        domain["runtime"].readiness,
        domain["runtime"].catalog,
        domain["runtime"].options,
        domain["runtime"].prices,
        entries_allowed=False,
    )
    assert not domain["client"].get("/api/mode").json()["entries_enabled"]


def test_settings_update_does_not_mutate_an_open_observation(domain):
    admitted(domain)
    view = domain["service"].settings.read()
    payload = view.settings.model_dump(mode="json")
    payload["risk"]["max_trades"] = 1
    r = domain["client"].put(
        "/api/settings",
        json=dict(expected_revision=view.revision, settings=payload),
        headers={"Idempotency-Key": "change-open"},
    )
    assert r.status_code == 409
    assert domain["wallet"].risk.max_trades == 20


@pytest.mark.parametrize(
    "extra", [{"armed": True}, {"kite_api_key": "secret"}, {"unknown": 1}]
)
def test_settings_import_rejects_unknown_or_secret_fields(domain, extra):
    view = domain["service"].settings.read()
    body = view.settings.model_dump(mode="json") | extra
    assert (
        post(
            domain,
            "/api/settings/import",
            dict(expected_revision=view.revision, settings=body),
            "import",
        ).status_code
        == 422
    )


def test_snapshot_and_socket_project_actual_wallet_positions_alerts_and_restart_cursor(
    domain,
):
    c, app = domain["client"], domain["app"]
    snapshot = c.get("/api/live/snapshot").json()
    assert (
        snapshot["wallet"]["balance"] == "100000.00"
        and "wallet" not in snapshot["unavailable"]
    )
    with c.websocket_connect(
        "wss://testserver/ws/live", headers={"Origin": "https://testserver"}
    ) as socket:
        initial = socket.receive_json()
        assert (
            initial["type"] == "snapshot"
            and initial["snapshot"]["wallet"]["mode"] == "PAPER"
        )
        assert (
            post(
                domain, "/api/wallet/deposit", {"amount": "1.00"}, "ws-deposit"
            ).status_code
            == 200
        )
        for _ in range(8):
            frame = socket.receive_json()
            if frame["type"] == "events" and any(
                e["kind"] == "status"
                and e["payload"].get("wallet", {}).get("balance") == "100001.00"
                for e in frame["events"]
            ):
                break
        else:
            pytest.fail("wallet status event missing")
    identity, trade = admitted(domain)
    after = c.get("/api/live/snapshot").json()
    assert after["positions"][0]["trade_id"] == trade
    assert any(e.kind == "position" for e in app.state.event_hub.events)
    assert any(e.kind == "trade" for e in app.state.event_hub.events)
    baseline = app.state.event_hub.sequence
    c.get("/api/live/snapshot")
    # Stable samples do not duplicate domain signal/trade/position events.
    assert not any(
        e.kind in ("signal", "trade", "position")
        for e in app.state.event_hub.since(app.state.event_hub.run_id, baseline)
    )


def test_default_unattached_domain_is_unavailable_not_a_fake_wallet(domain):
    del domain["app"].state.paper_execution
    del domain["app"].state.paper_runtime
    for path in (
        "/api/wallet",
        "/api/positions/open",
        "/api/trades",
        "/api/pnl/summary",
    ):
        assert domain["client"].get(path).status_code == 409
    assert not domain["client"].get("/api/mode").json()["entries_enabled"]
    snapshot = domain["client"].get("/api/live/snapshot").json()
    assert snapshot["wallet"] is None and snapshot["pnl"] is None


def test_readonly_preview_has_no_domain_or_market_mutation(domain):
    from app.db.models import StrategyDecision
    from app.strategy.models import SignalInput

    with Session(domain["wallet"].engine) as db:
        result = json.loads(
            db.get(IndicatorResult, ("api-test", domain["index"])).payload
        )
    signal = SignalInput.from_indicator("api-test", result, domain["ordinal"])
    before = domain["wallet"].snapshot()
    with Session(domain["wallet"].engine) as db:
        count = len(db.scalars(select(StrategyDecision)).all())
    response = post(
        domain,
        "/api/strikes/preview",
        dict(signal=signal.model_dump(mode="json"), free_capital="100000"),
        "preview",
    )
    assert response.status_code == 200 and not response.json()["executable"]
    assert (
        domain["wallet"].snapshot() == before
        and domain["app"].state.market_service.worker is None
    )
    with Session(domain["wallet"].engine) as db:
        assert len(db.scalars(select(StrategyDecision)).all()) == count


def test_command_crash_after_wallet_commit_recovers_without_second_deposit(domain):
    s, w = domain["service"], domain["wallet"]

    def interrupted():
        w.deposit("recovery", D(10), domain["wall"][0])
        raise RuntimeError("crash before command completion")

    with pytest.raises(RuntimeError):
        s.commands.run("recover", "deposit", "10", interrupted)
    assert w.snapshot().balance == 100010

    def resume():
        w.deposit("recovery", D(10), domain["wall"][0])
        return "done"

    assert s.commands.run("recover", "deposit", "10", resume) == "done"
    assert (
        s.commands.run(
            "recover", "deposit", "10", lambda: pytest.fail("must use saved result")
        )
        == "done"
    )
    assert w.snapshot().balance == 100010


def test_domain_migration_is_additive_and_preserves_previous_rows(
    tmp_path, monkeypatch
):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0010_wallet")
    engine = database_engine(url)
    before = set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO strategy_decisions VALUES "
            "('old','signal','2026-10-28T10:00:00+05:30','{}','{}','[]',?)",
            (json.dumps(dict(accepted=False, reason="quote_unavailable")),),
        )
    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) - before == {
        "domain_commands",
        "domain_decisions",
        "dashboard_settings_versions",
    }
    with Session(engine) as db:
        assert json.loads(db.get(DomainDecision, ("PAPER", "old")).payload)[
            "reasons"
        ] == ["quote_unavailable"]
    command.downgrade(config, "0010_wallet")
    assert set(inspect(engine).get_table_names()) == before
    engine.dispose()


@pytest.fixture(scope="session")
def compiled_client(tmp_path_factory):
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    output = tmp_path_factory.mktemp("typed-client")
    compiler = root / "tools/api-contracts/node_modules/typescript/lib/tsc.js"
    args = [
        "node",
        str(compiler),
        "--outDir",
        str(output),
        "--rootDir",
        str(root),
        "--target",
        "es2022",
        "--module",
        "commonjs",
        "--strict",
        "--lib",
        "es2022,dom",
        str(root / "frontend/src/api/client.ts"),
    ]
    built = subprocess.run(args, capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    return root, output / "frontend/src/api/client.js"


def test_real_frontend_client_auth_actions_and_resync(domain, compiled_client):
    import socket
    import subprocess
    import threading
    import time

    import uvicorn

    root, module = compiled_client
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(domain["app"], log_level="error", lifespan="on")
    )
    thread = threading.Thread(
        target=lambda: server.run(sockets=[listener]), daemon=True
    )
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        result = subprocess.run(
            [
                "node",
                str(root / "tools/api-contracts/client-integration.cjs"),
                str(module),
                f"http://127.0.0.1:{port}",
                str(domain["index"]),
                str(domain["ordinal"]),
            ],
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert '"result":"passed"' in result.stdout
        assert domain["wallet"].snapshot().balance == D("100007.34")
        assert domain["wallet"].snapshot().day_trades == 1
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()


def test_settings_command_recovers_commit_without_an_extra_version(domain):
    s = domain["service"]
    prior = s.settings.read()
    body = SettingsUpdate(expected_revision=prior.revision, settings=prior.settings)

    def interrupted():
        s.settings.update(body, "settings-recover")
        raise RuntimeError("after settings commit")

    with pytest.raises(RuntimeError):
        s.commands.run(
            "settings-recover", "settings-update", body.model_dump_json(), interrupted
        )

    def resume():
        return s.settings.update(body, "settings-recover").model_dump_json()

    value = s.commands.run(
        "settings-recover", "settings-update", body.model_dump_json(), resume
    )
    assert json.loads(value)["revision"] == prior.revision + 1
    assert s.settings.read().revision == prior.revision + 1


def test_prepare_and_confirm_recover_without_new_decision_or_trade(domain):
    from app.db.models import StrategyDecision

    s = domain["service"]

    def interrupted_prepare():
        s.prepare("api-test", domain["index"], domain["ordinal"], "recover-prepare")
        raise RuntimeError("after candidate commit")

    with pytest.raises(RuntimeError):
        s.commands.run("recover-prepare", "prepare", "same", interrupted_prepare)
    candidate = s.commands.run(
        "recover-prepare",
        "prepare",
        "same",
        lambda: s.prepare(
            "api-test", domain["index"], domain["ordinal"], "recover-prepare"
        ).model_dump_json(),
    )
    identity = json.loads(candidate)["decision_id"]
    with Session(s.engine) as db:
        assert len(db.scalars(select(StrategyDecision)).all()) == 1

    def interrupted_confirm():
        value = s.confirm(identity)
        assert value.accepted
        raise RuntimeError("after admission commit")

    with pytest.raises(RuntimeError):
        s.commands.run("recover-confirm", "confirm", identity, interrupted_confirm)
    del domain["app"].state.paper_runtime
    recovered = s.commands.run(
        "recover-confirm",
        "confirm",
        identity,
        lambda: s.confirm(identity).model_dump_json(),
    )
    assert (
        json.loads(recovered)["accepted"]
        and domain["wallet"].snapshot().day_trades == 1
    )


def test_prepared_or_confirmed_requests_cannot_import_quotes_readiness_or_live_flags(
    domain,
):
    identity = prepared(domain)
    for body in ({"ready": True}, {"quotes": {}}, {"armed": True}, {"mode": "LIVE"}):
        assert (
            post(
                domain, f"/api/decisions/{identity}/confirm", body, "invalid"
            ).status_code
            == 422
        )
    assert not domain["wallet"].snapshot().positions


def test_canonical_preview_can_succeed_without_subscribing_or_saving_a_decision(domain):
    from unittest.mock import Mock

    from test_option_preview import seed

    from app.db.models import StrategyDecision
    from app.strategy.models import SignalInput

    runtime = domain["runtime"]
    seed(domain["wallet"].engine, runtime.catalog())
    with Session(domain["wallet"].engine) as db:
        row = db.get(IndicatorResult, ("api-test", domain["index"]))
        signal = SignalInput.from_indicator(
            "api-test", json.loads(row.payload), domain["ordinal"]
        )
    worker = Mock()
    worker.running = worker.connected = True
    worker._history_ready.is_set.return_value = True
    worker.gap_required = False
    worker.option_quotes.snapshot.return_value = runtime.options()
    market = domain["app"].state.market_service
    market.worker = worker
    try:
        before = domain["wallet"].snapshot()
        response = post(
            domain,
            "/api/strikes/preview",
            dict(signal=signal.model_dump(mode="json"), free_capital="100000"),
            "preview-ready",
        )
        assert response.status_code == 200 and response.json()["accepted"], (
            response.text
        )
        assert (
            response.json()["decision_id"] is None and not response.json()["executable"]
        )
        assert domain["wallet"].snapshot() == before
        assert not worker.set_option_contracts.called
        with Session(domain["wallet"].engine) as db:
            assert db.scalars(select(StrategyDecision)).all() == []
    finally:
        market.worker = None


def test_new_domain_producers_do_not_break_feed_snapshot_before_domain_migrations(
    tmp_path, monkeypatch
):
    url = f"sqlite:///{(tmp_path / 'older.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "0006_dashboard_api")
    app = create_app(
        Settings(
            _env_file=None, database_url=url, dashboard_password_hash=password_hash()
        )
    )
    c = TestClient(app, base_url="https://testserver")
    try:
        # authenticate() creates all current tables; this test must retain the
        # actual older migration boundary instead of upgrading its fixture.
        login = c.post(
            "/api/auth/dashboard/login", json={"password": "fixture-password-only"}
        )
        assert login.status_code == 200
        response = c.get("/api/live/snapshot")
        assert response.status_code == 200, response.text
        assert (
            response.json()["wallet"] is None
            and "signals" in response.json()["unavailable"]
        )
        assert c.get("/api/settings").status_code == 503
    finally:
        app.state.market_service.auth.close()
        app.state.database_engine.dispose()


def test_settings_schema_import_defaults_and_pine_rebuild_validation(domain):
    c, s = domain["client"], domain["service"]
    schema = c.get("/api/settings/schema")
    assert schema.status_code == 200 and "atrLen" in schema.json()["pine_inputs"]
    current = s.settings.read()
    body = current.settings.model_dump(mode="json")
    body["pine"]["unknown_secret"] = True
    assert (
        post(
            domain,
            "/api/settings/import",
            dict(expected_revision=current.revision, settings=body),
            "bad-pine",
        ).status_code
        == 422
    )
    body = current.settings.model_dump(mode="json")
    body["pine"]["rsiLen"] = 3
    r = post(
        domain,
        "/api/settings/import",
        dict(expected_revision=current.revision, settings=body),
        "pine-needs-rebuild",
    )
    assert r.status_code == 409
    r = post(
        domain,
        "/api/settings/import",
        dict(expected_revision=current.revision, settings=body, rebuild=True),
        "pine-rebuild",
    )
    assert r.status_code == 200 and r.json()["requires_rebuild"]
    with pytest.raises(ValueError):
        s.rebind_wallet("api-test")


def test_owner_rebind_accepts_verified_rebuilt_grid_without_overwriting_old_stream(
    domain,
):
    s, w = domain["service"], domain["wallet"]
    previous = s.settings.read()
    desired = previous.settings.model_dump(mode="json")
    desired["data"]["box"] = "25"
    desired["pine"]["boxSize"] = 25.0
    chosen = s.settings.update(
        SettingsUpdate(
            expected_revision=previous.revision,
            settings=SettingsBundle.model_validate(desired),
            rebuild=True,
        )
    )
    pine = IndicatorSettings(**chosen.settings.pine)
    repo = IndicatorRepository(w.engine, "rebuilt", pine)
    with Session(w.engine) as db, db.begin():
        db.add(
            MarketCheckpoint(
                stream="rebuilt",
                revision=1,
                state="{}",
                configuration=encode(
                    dict(
                        spot=111,
                        future=222,
                        box="25",
                        anchor="23900",
                        mode="minute_close",
                    )
                ),
            )
        )
        b = Brick(0, D(23900), D(23925), 1, domain["wall"][0])
        db.add(StoredBrick(stream="rebuilt", index=0, payload=encode(asdict(b))))
    repo.process(b)
    publish_chart_history(w.engine, "rebuilt")
    before = w.snapshot()
    assert s.rebind_wallet("rebuilt") is w
    assert (
        w.snapshot().ledger == before.ledger and w.snapshot().balance == before.balance
    )
    assert (
        s.market.settings.market_stream == "rebuilt"
        and s.market.settings.renko_box == 25
    )
    with Session(w.engine) as db:
        assert db.get(MarketCheckpoint, "api-test") is not None
