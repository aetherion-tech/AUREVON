"""Isolated inbox security, source fences and two-sided nonexecuting comparison."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from auth_helpers import authenticate, password_hash
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.shadow import ShadowEvent, source
from app.config import Settings
from app.db.models import (
    AuditEntry,
    Base,
    IndicatorCheckpoint,
    IndicatorEvent,
    IndicatorResult,
    MarketCheckpoint,
    PaperExecutionBook,
    ShadowReceipt,
    StrategyDecision,
)
from app.main import create_app

TOKEN = "synthetic-ingress-only-" + "a" * 32


@pytest.fixture
def shadow(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{(tmp_path / 'shadow.db').as_posix()}",
            market_lock_file=tmp_path / "owner.lock",
            dashboard_password_hash=password_hash(),
            shadow_ingestion_enabled=True,
            shadow_stream="synthetic-shadow",
            shadow_webhook_secret=TOKEN,
        )
    )
    engine = app.state.database_engine
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        db.add(
            MarketCheckpoint(
                stream="synthetic-shadow",
                revision=1,
                configuration='{"box":"50"}',
                state="{}",
            )
        )
        db.add(IndicatorCheckpoint(stream="synthetic-shadow", index=12, payload="{}"))
        db.add(
            IndicatorResult(
                stream="synthetic-shadow",
                index=12,
                input='{"settings":{"boxSize":50}}',
                payload="{}",
            )
        )
        for index, kind in ((6, "ENTRY"), (8, "EXIT"), (11, "ENTRY")):
            db.add(
                IndicatorEvent(
                    stream="synthetic-shadow",
                    index=index,
                    ordinal=0,
                    kind=kind,
                    payload=json.dumps(
                        {
                            "kind": kind,
                            "type": "CORE",
                            "direction": 1,
                            "trade_id": f"trade-{index}",
                        }
                    ),
                )
            )
    with TestClient(app, base_url="https://testserver") as client:
        yield client, app


def message(app, **changes):
    with Session(app.state.database_engine) as db:
        identity, _ = source(db, "synthetic-shadow")
    body = dict(
        event_id="tv-6",
        source_id=identity,
        brick_index=6,
        at=datetime.now(timezone.utc).isoformat(),
        kind="ENTRY",
        family="CO",
        direction=1,
        trade_id="trade-6",
    )
    body.update(changes)
    return body


def test_ingress_auth_audit_validation_dedup_and_no_financial_side_effects(shadow):
    client, app = shadow
    url = "/api/shadow/tv-alert"
    body = message(app)
    assert client.post(url, json=body).status_code == 401
    headers = {"Authorization": "Bearer " + TOKEN}
    assert client.post(url, json=body, headers=headers).json()["status"] == "recorded"
    assert client.post(url, json=body, headers=headers).json()["status"] == "duplicate"
    assert (
        client.post(url, json=body | {"family": "DIV"}, headers=headers).status_code
        == 409
    )
    assert (
        client.post(
            url, json=message(app, source_id="0" * 64), headers=headers
        ).status_code
        == 409
    )
    assert (
        client.post(url, json=message(app, brick_index=15), headers=headers).status_code
        == 409
    )
    assert (
        client.post(
            url,
            json=message(
                app, at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            ),
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(url, json=body | {"place_order": True}, headers=headers).status_code
        == 422
    )
    assert (
        client.post(
            url,
            content="x" * 8193,
            headers=headers | {"Content-Type": "application/json"},
        ).status_code
        == 413
    )
    assert client.post(url, content="x", headers=headers).status_code == 415
    with Session(app.state.database_engine) as db:
        assert db.scalar(select(func.count()).select_from(ShadowReceipt)) == 1
        assert db.scalar(select(func.count()).select_from(PaperExecutionBook)) == 0
        assert db.scalar(select(func.count()).select_from(StrategyDecision)) == 0
        audits = db.scalars(select(AuditEntry)).all()
        assert all(row.status is not None for row in audits)
        assert TOKEN not in repr([(row.action, row.actor) for row in audits])
    app.state.shadow_service.settings.shadow_ingestion_enabled = False
    assert client.post(url, json=body, headers=headers).status_code == 404


def test_comparison_is_authenticated_two_sided_and_waits_for_window(shadow):
    client, app = shadow
    assert client.get("/api/shadow/status").status_code == 401
    authenticate(client)
    service = app.state.shadow_service
    now = datetime.now(timezone.utc)
    service.receive(ShadowEvent.model_validate(message(app)), now)
    service.receive(
        ShadowEvent.model_validate(
            message(app, event_id="only-tv", brick_index=3, trade_id="only-tv")
        ),
        now,
    )
    result = client.get("/api/shadow/comparison?start=0&end=12").json()
    assert result["matched"] == 1
    assert result["pending"] == 1
    assert result["missing_tradingview"] == ["synthetic-shadow:8:0"]
    assert result["missing_backend"] == ["only-tv"]
    assert result["reference_verified"] is False
    assert client.get("/api/shadow/comparison?start=0&end=501").status_code == 422
    assert client.get("/api/shadow/comparison?start=0&end=13").status_code == 409


def test_one_receipt_cannot_satisfy_two_events_and_source_change_is_fenced(shadow):
    _, app = shadow
    service = app.state.shadow_service
    service.receive(
        ShadowEvent.model_validate(message(app)), datetime.now(timezone.utc)
    )
    with Session(app.state.database_engine) as db, db.begin():
        first = db.get(IndicatorEvent, ("synthetic-shadow", 6, 0))
        db.add(
            IndicatorEvent(
                stream=first.stream,
                index=7,
                ordinal=0,
                kind=first.kind,
                payload=first.payload,
            )
        )
    result = service.compare(0, 12)
    assert result.matched == 1 and len(result.missing_tradingview) == 2
    old = message(app, event_id="old-source")
    with Session(app.state.database_engine) as db, db.begin():
        db.get(MarketCheckpoint, "synthetic-shadow").configuration = '{"box":"100"}'
    with pytest.raises(HTTPException) as rejected:
        service.receive(ShadowEvent.model_validate(old), datetime.now(timezone.utc))
    assert rejected.value.status_code == 409
    assert service.compare(0, 12).matched == 0


def test_durable_rate_limit_and_retries_do_not_consume_allowance(shadow):
    _, app = shadow
    service = app.state.shadow_service
    now = datetime.now(timezone.utc)
    first = ShadowEvent.model_validate(message(app))
    service.receive(first, now)
    for _ in range(3):
        assert service.receive(first, now)["status"] == "duplicate"
    for index in range(1, 60):
        service.receive(first.model_copy(update={"event_id": f"tv-{index + 100}"}), now)
    with pytest.raises(HTTPException) as limited:
        service.receive(first.model_copy(update={"event_id": "exceeds-limit"}), now)
    assert limited.value.status_code == 429
