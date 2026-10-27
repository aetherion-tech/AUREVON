"""Isolated dashboard API integration: access, durability, ordering and replay."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from auth_helpers import authenticate, password_hash
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.api.dashboard_routes import COOKIE
from app.api.event_hub import EventHub
from app.api.live_contracts import TickData, TradeData
from app.broker.kite_auth import IST
from app.config import Settings
from app.db.models import (
    AuditEntry,
    Base,
    DashboardSecurityState,
    MarketCheckpoint,
    StoredBrick,
)
from app.main import create_app
from app.market.persistence import encode


@pytest.fixture
def dashboard(tmp_path):
    config = Settings(
        _env_file=None,
        dashboard_password_hash=SecretStr(password_hash()),
        database_url=f"sqlite:///{(tmp_path / 'dashboard.db').as_posix()}",
        market_record_dir=tmp_path / "recordings",
        market_lock_file=tmp_path / "market.lock",
    )
    app = create_app(config)
    Base.metadata.create_all(app.state.database_engine)
    with TestClient(app, base_url="https://testserver") as client:
        authenticate(client)
        yield client, app, config


def test_mutation_auth_csrf_origin_and_safe_durable_audit(dashboard):
    client, app, _ = dashboard
    anonymous = TestClient(app, base_url="https://testserver")
    assert anonymous.post("/api/market/service/stop").status_code == 401
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/market/service/stop").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert (
        client.post(
            "/api/market/service/stop", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/market/service/stop?secret=private-value",
            json={"password": "private-value"},
        ).status_code
        == 200
    )
    with Session(app.state.database_engine) as db:
        rows = db.scalars(select(AuditEntry)).all()
        assert [r.status for r in rows] == [200, 401, 403, 403, 200]
        assert rows[-1].action == "POST /api/market/service/stop"
        assert "private-value" not in repr(
            [(r.action, r.actor, r.request_id) for r in rows]
        )


def test_audit_schema_missing_fails_closed(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{(tmp_path / 'empty.db').as_posix()}",
            dashboard_password_hash=SecretStr(password_hash()),
        )
    )
    client = TestClient(app, base_url="https://testserver")
    assert (
        client.post(
            "/api/auth/dashboard/login", json={"password": "fixture-password-only"}
        ).status_code
        == 503
    )
    assert not client.cookies.get(COOKIE)


def test_five_failures_lockout_survives_restart_and_expires(dashboard):
    client, app, config = dashboard
    for _ in range(4):
        assert (
            client.post(
                "/api/auth/dashboard/login", json={"password": "wrong"}
            ).status_code
            == 401
        )
    fifth = client.post("/api/auth/dashboard/login", json={"password": "wrong"})
    assert fifth.status_code == 429 and fifth.headers["retry-after"] == "900"
    restarted = TestClient(create_app(config), base_url="https://testserver")
    assert (
        restarted.post(
            "/api/auth/dashboard/login", json={"password": "fixture-password-only"}
        ).status_code
        == 429
    )
    with Session(app.state.database_engine) as db:
        locked = db.get(DashboardSecurityState, "operator")
        until = datetime.fromisoformat(locked.locked_until).timestamp()
    with patch("app.api.dashboard_routes.time", return_value=until + 1):
        # JWT iat is in the future under this clock; login itself still resets lock.
        assert (
            restarted.post(
                "/api/auth/dashboard/login", json={"password": "fixture-password-only"}
            ).status_code
            == 200
        )
    with Session(app.state.database_engine) as db:
        assert db.get(DashboardSecurityState, "operator").failures == 0


def test_snapshot_no_secrets_and_disabled_readiness(dashboard):
    client, app, _ = dashboard
    snapshot = client.get("/api/live/snapshot")
    assert snapshot.status_code == 200, snapshot.text
    data = snapshot.json()
    assert data["mode"] == "PAPER" and not data["armed"] and not data["entries_enabled"]
    assert data["selected"] is None
    assert data["quality"]["history_pending"]
    assert "positions" in data["unavailable"]
    for forbidden in (
        "recording_directory",
        "access_token",
        "api_secret",
        "password_hash",
    ):
        assert forbidden not in snapshot.text
    assert data["run_id"] == app.state.event_hub.run_id
    anonymous = TestClient(app)
    assert anonymous.get("/api/live/snapshot").status_code == 401


def test_alert_persistence_idempotent_ack_and_transport(dashboard):
    client, app, _ = dashboard
    live = app.state.live_service
    value = live.raise_alert("reconciliation_mismatch")
    assert live.raise_alert("reconciliation_mismatch").id == value.id
    response = client.get("/api/alerts?limit=1")
    assert response.json()["items"][0]["id"] == value.id
    first = client.post(f"/api/alerts/{value.id}/ack")
    second = client.post(f"/api/alerts/{value.id}/ack")
    assert first.status_code == 200 and first.json() == second.json()
    assert first.json()["acknowledged_at"] is not None
    assert client.post("/api/alerts/missing/ack").status_code == 404
    assert app.state.event_hub.events[-1].kind == "alert"


def test_history_keyset_and_revision_fence(dashboard):
    client, app, _ = dashboard
    at = datetime(2026, 10, 23, 10, tzinfo=IST)
    with Session(app.state.database_engine) as db, db.begin():
        db.add(
            MarketCheckpoint(
                stream="test",
                revision=3,
                configuration=encode(
                    {"spot": 1, "future": 2, "box": "50", "anchor": "100"}
                ),
                state="{}",
            )
        )
        for i in range(1, 4):
            db.add(
                StoredBrick(
                    stream="test",
                    index=i,
                    payload=encode(
                        {
                            "index": i,
                            "open": "100",
                            "close": "150",
                            "direction": 1,
                            "ts": at.isoformat(),
                            "volume": "0",
                        }
                    ),
                )
            )
    first = client.get("/api/bricks?stream=test&limit=2")
    assert first.status_code == 200, first.text
    assert first.json()["next_after"] == 2
    second = client.get("/api/bricks?stream=test&limit=2&after=2&revision=3")
    assert [r["index"] for r in second.json()["items"]] == [3]
    assert second.json()["next_after"] is None
    assert client.get("/api/bricks?stream=test&revision=2").status_code == 409
    assert client.get("/api/bricks?stream=missing").status_code == 404
    assert client.get("/api/candles?stream=test&token=9").status_code == 422


def test_websocket_requires_cookie_and_origin(dashboard):
    client, app, _ = dashboard
    for other, headers in (
        (TestClient(app), {"Origin": "https://testserver"}),
        (client, {"Origin": "https://evil.example"}),
    ):
        with pytest.raises(WebSocketDisconnect) as error:
            with other.websocket_connect("wss://testserver/ws/live", headers=headers):
                pass
        assert error.value.code == 1008
    with client.websocket_connect(
        "wss://testserver/ws/live", headers={"Origin": "https://testserver"}
    ) as socket:
        initial = socket.receive_json()
        assert initial["type"] == "snapshot"
        assert initial["snapshot"]["sequence"] <= app.state.event_hub.sequence


def test_websocket_reconnect_event_order_and_run_resync(dashboard):
    client, app, _ = dashboard
    hub = app.state.event_hub
    snapshot = client.get("/api/live/snapshot").json()
    app.state.live_service.raise_alert("risk_reject")
    with client.websocket_connect(
        f"wss://testserver/ws/live?run_id={hub.run_id}&after={snapshot['sequence']}",
        headers={"Origin": "https://testserver"},
    ) as socket:
        batch = socket.receive_json()
        assert batch["type"] == "events"
        sequences = [e["sequence"] for e in batch["events"]]
        assert sequences == sorted(set(sequences))
        assert all(s > snapshot["sequence"] for s in sequences)
    with client.websocket_connect(
        "wss://testserver/ws/live?run_id=old&after=0",
        headers={"Origin": "https://testserver"},
    ) as socket:
        assert socket.receive_json()["type"] == "resync_required"


def test_hub_throttle_overflow_and_reliable_kind_order():
    hub = EventHub(capacity=3)
    tick = TickData(token=1, price=Decimal("100"), time=datetime.now(IST))
    assert hub.publish(tick) is not None
    assert hub.publish(tick) is None
    for i in range(4):
        hub.publish(TradeData(trade_id=str(i), event="test"))
    assert len(hub.events) == 3
    assert hub.since(hub.run_id, 0) is None
    assert [e.sequence for e in hub.since(hub.run_id, 2)] == [3, 4, 5]
    assert hub.since("different-run", 5) is None
    assert hub.since(hub.run_id, 100) is None


def test_expired_session_rejected_on_websocket(dashboard):
    client, app, _ = dashboard
    app.state.dashboard_sessions._expires = 0
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "wss://testserver/ws/live", headers={"Origin": "https://testserver"}
        ):
            pass


def test_logout_revokes_active_websocket(dashboard):
    client, _, _ = dashboard
    with client.websocket_connect(
        "wss://testserver/ws/live", headers={"Origin": "https://testserver"}
    ) as socket:
        assert socket.receive_json()["type"] == "snapshot"
        assert client.post("/api/auth/dashboard/logout").status_code == 200
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 1008


def test_slow_websocket_send_is_closed_without_unbounded_queue(dashboard, monkeypatch):
    client, _, _ = dashboard
    from starlette.websockets import WebSocket

    async def slow_send(*args, **kwargs):
        raise TimeoutError

    monkeypatch.setattr(WebSocket, "send_json", slow_send)
    with client.websocket_connect(
        "wss://testserver/ws/live", headers={"Origin": "https://testserver"}
    ) as socket:
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 1013


@pytest.mark.parametrize(
    "body,status",
    [
        ({"mode": "PAPER"}, 200),
        ({"mode": "PAPER", "armed": True}, 409),
        ({"mode": "LIVE", "confirm": "LIVE"}, 403),
    ],
)
def test_mode_cannot_arm_or_enable_live_orders(dashboard, body, status):
    client, _, _ = dashboard
    assert client.post("/api/mode", json=body).status_code == status
    mode = client.get("/api/mode").json()
    assert mode["mode"] == "PAPER" and not mode["armed"]
    assert not mode["live_orders_enabled"] and not mode["entries_enabled"]


def test_replay_disabled_and_live_feed_conflict(dashboard):
    client, app, config = dashboard
    body = {
        "source_run": "a" * 32,
        "files": ["2026-10-23.jsonl"],
        "spot_token": 1,
        "future_token": 2,
        "box": "50",
        "anchor": "100",
    }
    assert client.post("/api/dev/replay", json=body).status_code == 404
    config.development_replay_enabled = True
    app.state.market_service.desired = True
    assert client.post("/api/dev/replay", json=body).status_code == 409
    app.state.market_service.desired = False
    body["files"] = ["../../secret.jsonl"]
    assert client.post("/api/dev/replay", json=body).status_code == 422


def test_dev_cors_explicit_and_no_wildcards(dashboard):
    client, _, _ = dashboard
    good = client.options(
        "/api/live/snapshot",
        headers={
            "Origin": "https://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert good.headers["access-control-allow-origin"] == "https://localhost:5173"
    assert good.headers["access-control-allow-credentials"] == "true"
    bad = client.options(
        "/api/live/snapshot",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in bad.headers
    with pytest.raises(ValueError):
        Settings(_env_file=None, dashboard_origins=["*"])
