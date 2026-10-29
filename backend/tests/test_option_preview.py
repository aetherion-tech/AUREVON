"""Authenticated preview, catalog provenance, decision persistence and migrations."""

import json
from datetime import UTC, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from alembic.config import Config
from auth_helpers import authenticate, password_hash
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from test_option_planner import NOW, calendar, capital, fixture

from alembic import command
from app.broker.kite_ticker import TickerWorker
from app.config import Settings
from app.db.models import Base, Instrument, InstrumentSnapshot, StrategyDecision
from app.db.session import database_engine
from app.indicator.settings import IndicatorSettings
from app.indicator.strategy import PineEngine
from app.main import create_app
from app.strategy.models import SignalInput
from app.strategy.service import load_catalog, preview


def seed(engine, cat):
    with Session(engine) as session, session.begin():
        session.add(
            InstrumentSnapshot(
                exchange="NFO",
                loaded_at=cat.loaded_at.astimezone(UTC),
                row_count=len(cat.contracts),
            )
        )
        for c in cat.contracts:
            session.add(
                Instrument(
                    exchange="NFO",
                    tradingsymbol=c.symbol,
                    instrument_token=c.token,
                    name="NIFTY",
                    segment="NFO-OPT",
                    expiry=c.expiry,
                    strike=c.strike,
                    tick_size=c.tick_size,
                    lot_size=c.lot_size,
                    instrument_type=c.option_type,
                )
            )


@pytest.fixture
def setup(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{(tmp_path / 'preview.db').as_posix()}",
            dashboard_password_hash=password_hash(),
        )
    )
    Base.metadata.create_all(app.state.database_engine)
    app.state.market_service.clock = lambda: NOW
    sig, cat, quotes, s = fixture()
    seed(app.state.database_engine, cat)
    worker = TickerWorker(Mock(), 111, 222)
    worker.running = worker.connected = True
    worker.option_quotes.configure(list(cat.contracts))
    worker.option_quotes.quotes = dict(quotes)
    app.state.market_service.worker = worker
    client = TestClient(app)
    yield client, app, sig, cat, quotes, s
    app.state.database_engine.dispose()
    app.state.market_service.auth.close()


def test_preview_login_csrf_and_nonexecuting_exact_response(setup):
    client, app, sig, cat, quotes, s = setup
    payload = {"signal": sig.model_dump(mode="json"), "free_capital": "100000"}
    assert client.post("/api/settings/preview-strikes", json=payload).status_code == 401
    authenticate(client)
    response = client.post("/api/settings/preview-strikes", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted"] and not body["executable"]
    assert isinstance(body["plan"]["credit"], str)
    assert isinstance(body["plan"]["maximum_loss"], str)
    assert Decimal(body["plan"]["credit"]) == Decimal("6712.50")
    assert Decimal(body["plan"]["maximum_loss"]) == Decimal("8287.50")
    assert body["plan"]["margin_source"] == "PAPER_ESTIMATE"
    assert body["plan"]["capital"]["source"] == "USER_PREVIEW"
    with Session(app.state.database_engine) as session:
        row = session.get(StrategyDecision, body["decision_id"])
        assert json.loads(row.payload) == body
        assert json.loads(row.quotes)
    socket = app.state.market_service.worker.socket
    socket.connect.assert_not_called()
    socket.place_order.assert_not_called()
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/settings/preview-strikes", json=payload).status_code == 403


def test_rejected_preview_persists_reason_and_does_not_mutate_catalog(setup):
    client, app, sig, cat, quotes, s = setup
    authenticate(client)
    response = client.post(
        "/api/settings/preview-strikes",
        json={"signal": sig.model_dump(mode="json"), "free_capital": "0"},
    )
    assert response.status_code == 200
    body = response.json()
    assert not body["accepted"] and body["reason"] == "insufficient_free_capital"
    assert body["attempts"]
    assert load_catalog(app.state.database_engine, NOW).contracts == cat.contracts


def test_no_worker_or_capital_never_yields_an_executable_plan(setup):
    client, app, sig, cat, quotes, s = setup
    authenticate(client)
    app.state.market_service.worker = None
    body = client.post(
        "/api/settings/preview-strikes", json={"signal": sig.model_dump(mode="json")}
    ).json()
    assert body["reason"] == "capital_unavailable" and not body["executable"]
    body = client.post(
        "/api/settings/preview-strikes",
        json={"signal": sig.model_dump(mode="json"), "free_capital": "100000"},
    ).json()
    assert not body["accepted"] and body["reason"] == "quote_unavailable"


def test_missing_or_stale_catalog_is_retained_as_rejected_decision(setup):
    client, app, sig, cat, quotes, s = setup
    authenticate(client)
    with Session(app.state.database_engine) as session, session.begin():
        session.get(InstrumentSnapshot, "NFO").loaded_at = NOW - timedelta(days=1)
    body = client.post(
        "/api/settings/preview-strikes", json={"signal": sig.model_dump(mode="json")}
    ).json()
    assert body["reason"] == "stale_catalog" and body["decision_id"]


def test_indicator_entry_bridge_uses_actual_signal_event_contract():
    from test_pine_strategy import brick

    engine = PineEngine(
        "test", IndicatorSettings(atrLen=2, rsiLen=2, minGrade="Weak and above (all)")
    )
    prices = [1000, 1050, 1100, 1150, 1100, 1050, 1000]
    for i in range(len(prices) - 1):
        result = engine.process(brick(i, prices[i], prices[i + 1]))
        for ordinal, event in enumerate(result["events"]):
            if event["kind"] == "ENTRY":
                mapped = SignalInput.from_indicator("test", result, ordinal)
                assert mapped.trade_id == event["trade_id"]
                assert mapped.spot == Decimal(str(event["price"]))
                assert mapped.family in ("CO", "DIV", "OT")
                return
    pytest.fail("fixture must produce an indicator entry")


def test_preview_uses_same_planner_and_records_rejected_inputs(tmp_path):
    db = database_engine(f"sqlite:///{(tmp_path / 'decisions.db').as_posix()}")
    Base.metadata.create_all(db)
    try:
        sig, cat, quotes, s = fixture()
        result = preview(db, sig, cat, quotes, capital(), NOW, calendar(), s)
        assert result.accepted
        rejected = preview(db, sig, cat, {}, capital(), NOW, calendar(), s)
        assert not rejected.accepted and rejected.attempts
        with Session(db) as session:
            assert len(session.scalars(select(StrategyDecision)).all()) == 2
    finally:
        db.dispose()


def test_additive_migration_preserves_rows_and_downgrades(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0007_indicator")
    db = database_engine(url)
    try:
        with db.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO market_lifecycle_state (key,payload) "
                "VALUES ('preserve','{}')"
            )
        before = set(inspect(db).get_table_names())
        command.upgrade(config, "0008_strategy")
        assert set(inspect(db).get_table_names()) == before | {"strategy_decisions"}
        with db.connect() as connection:
            assert (
                connection.exec_driver_sql(
                    "SELECT count(*) FROM market_lifecycle_state WHERE key='preserve'"
                ).scalar_one()
                == 1
            )
        command.downgrade(config, "0007_indicator")
        assert set(inspect(db).get_table_names()) == before
        command.upgrade(config, "0008_strategy")
    finally:
        db.dispose()


def test_invalid_catalog_is_a_durable_rejection(setup):
    client, app, sig, cat, quotes, s = setup
    authenticate(client)
    with Session(app.state.database_engine) as session, session.begin():
        row = session.get(Instrument, ("NFO", cat.contracts[0].symbol))
        row.tick_size = 0
    body = client.post(
        "/api/settings/preview-strikes", json={"signal": sig.model_dump(mode="json")}
    ).json()
    assert body["reason"] == "invalid_option_catalog" and body["decision_id"]


def test_preview_subscription_keeps_pinned_contracts_without_starting_feed(setup):
    from unittest.mock import patch

    client, app, sig, cat, quotes, s = setup
    authenticate(client)
    worker = app.state.market_service.worker
    pin = cat.contracts[0]
    worker.option_quotes.configure(list(cat.contracts), [pin])
    with patch(
        "twisted.internet.reactor.callFromThread", side_effect=lambda f, *a: f(*a)
    ):
        response = client.post(
            "/api/settings/preview-strikes",
            json={
                "signal": sig.model_dump(mode="json"),
                "free_capital": "100000",
                "subscribe_quotes": True,
            },
        )
    assert response.status_code == 200 and response.json()["accepted"]
    assert pin.token in worker.option_quotes.tokens
    worker.socket.connect.assert_not_called()


def test_missing_decision_migration_blocks_preview_result(setup):
    client, app, sig, cat, quotes, s = setup
    authenticate(client)
    StrategyDecision.__table__.drop(app.state.database_engine)
    response = client.post(
        "/api/settings/preview-strikes",
        json={"signal": sig.model_dump(mode="json"), "free_capital": "100000"},
    )
    assert response.status_code == 503
