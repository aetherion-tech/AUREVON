"""Contract boundaries: exact INR, aware IST, safe errors and published schemas."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from app.api.schemas import (
    Contract,
    DateRangeRequest,
    EventEnvelope,
    ExchangeDate,
    HealthResponse,
    ISTTimestamp,
    Page,
    Pagination,
    PaginationRequest,
    RupeeAmount,
)
from app.broker.kite_auth import AuthError, KiteAuth, KiteStatus
from app.config import Settings
from app.main import create_app


class Balance(Contract):
    amount: RupeeAmount


def test_exact_inr_json_preserves_paise_beyond_javascript_precision():
    balance = Balance(amount="9007199254740993.01")
    assert balance.amount == Decimal("9007199254740993.01")
    assert balance.model_dump(mode="json") == {"amount": "9007199254740993.01"}
    assert Balance(amount=Decimal("-1.2")).model_dump_json() == '{"amount":"-1.20"}'
    assert (
        Balance.model_json_schema(mode="validation")["properties"]["amount"]["type"]
        == "string"
    )
    assert (
        Balance.model_json_schema(mode="serialization")["properties"]["amount"]["type"]
        == "string"
    )


@pytest.mark.parametrize(
    "amount", [1.01, 1, True, "NaN", "Infinity", "0.001", "10000000000000000.00"]
)
def test_money_rejects_float_nonfinite_excess_precision_and_overflow(amount):
    with pytest.raises(ValidationError):
        Balance(amount=amount)


def test_aware_ist_timestamps_and_exchange_dates_are_distinct():
    time = TypeAdapter(ISTTimestamp)
    actual = time.validate_python(datetime(2026, 10, 25, 20, tzinfo=UTC))
    assert actual.isoformat() == "2026-10-26T01:30:00+05:30"
    assert time.dump_python(actual, mode="json") == "2026-10-26T01:30:00+05:30"
    for value in (datetime(2026, 10, 26), "2026-10-26T01:30:00", 1790000000):
        with pytest.raises(ValidationError):
            time.validate_python(value)
    date_type = TypeAdapter(ExchangeDate)
    assert date_type.validate_python("2026-10-26") == date(2026, 10, 26)
    for value in (
        "2026-10-26T00:00:00Z",
        datetime(2026, 10, 26, tzinfo=UTC),
        1790000000,
    ):
        with pytest.raises(ValidationError):
            date_type.validate_python(value)
    with pytest.raises(ValidationError):
        DateRangeRequest(start="2026-10-27", end="2026-10-26")


def test_pagination_bounds_known_unknown_totals_and_typed_payloads():
    assert PaginationRequest(limit="25").limit == 25
    for values in (
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
        {"offset": 1_000_001},
        {"limit": True},
        {"limit": "1.0"},
    ):
        with pytest.raises(ValidationError):
            PaginationRequest(**values)
    page = Page[int](
        items=[1, 2], pagination=Pagination(limit=2, offset=0, total=3, next_offset=2)
    )
    assert page.model_dump(mode="json")["pagination"]["next_offset"] == 2
    assert Page[int](items=[], pagination=Pagination(offset=50, total=1)).items == []
    assert Page[int](items=[1], pagination=Pagination()).pagination.total is None
    for page in (
        {"items": [1, 2, 3], "pagination": {"limit": 2}},
        {"items": [1, 2], "pagination": {"limit": 2, "total": 1}},
        {"items": [1], "pagination": {"limit": 2, "next_offset": 2}},
    ):
        with pytest.raises(ValidationError):
            Page[int].model_validate(page)


def test_versioned_events_bind_payload_and_never_enable_trading():
    event = EventEnvelope[HealthResponse](
        run_id="a" * 32,
        sequence=1,
        kind="status",
        at="2026-10-26T00:00:00Z",
        payload={"application": "AUREVON"},
    )
    wire = event.model_dump(mode="json")
    assert wire["api_version"] == "1.0" and wire["at"].endswith("+05:30")
    assert wire["payload"]["live_orders_enabled"] is False
    for update in (
        {"api_version": "2.0"},
        {"sequence": 0},
        {"payload": {"application": "A", "live_orders_enabled": True}},
        {"unexpected": "field"},
    ):
        with pytest.raises(ValidationError):
            EventEnvelope[HealthResponse].model_validate(wire | update)


@pytest.fixture
def api(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'contracts.db').as_posix()}",
    )
    auth = Mock(spec=KiteAuth)
    auth.status.return_value = KiteStatus(
        configured=True,
        message="fixture",
        expires_at=datetime(2026, 10, 26, 0, tzinfo=UTC),
    )
    app = create_app(settings, auth)

    @app.get("/fixture/fault")
    def fault():
        raise RuntimeError("private-token-internal-error")

    @app.get("/fixture/http-error")
    def custom_error():
        raise HTTPException(499, "private-token-http-detail")

    @app.post("/fixture/money")
    def money(value: Balance) -> Balance:
        return value

    with TestClient(app) as client:
        yield client, auth, app


def test_existing_wire_shape_and_ist_response(api):
    client, _, _ = api
    health = client.get("/api/health")
    assert health.json() == {
        "status": "ok",
        "application": "AUREVON",
        "mode": "PAPER",
        "live_orders_enabled": False,
    }
    assert health.headers["X-AUREVON-API-Version"] == "1.0"
    auth = client.get("/api/auth/kite/status")
    assert auth.json()["expires_at"] == "2026-10-26T05:30:00+05:30"


def test_openapi_models_match_errors_and_existing_instrument_routes(api):
    client, _, _ = api
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "303" in paths["/api/auth/kite/login"]["get"]["responses"]
    assert paths["/api/market/nifty"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/NiftyResponse")
    for path, methods in paths.items():
        for name, route in methods.items():
            if name not in ("get", "post"):
                continue
            assert route["responses"]["422"]["content"]["application/json"]["schema"][
                "$ref"
            ].endswith("/ErrorEnvelope")


@pytest.mark.parametrize(
    "path,method,status",
    [
        ("/missing", "get", 404),
        ("/api/health", "post", 405),
        ("/api/market/nifty?expiry=private-token-value", "get", 422),
        ("/fixture/fault", "get", 500),
        ("/fixture/http-error", "get", 499),
    ],
)
def test_uniform_errors_never_reflect_private_values(api, path, method, status):
    client, _, _ = api
    response = getattr(client, method)(path)
    assert response.status_code == status
    envelope = response.json()["error"]
    assert {"code", "message", "request_id", "details"} == set(envelope)
    assert envelope["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["X-AUREVON-API-Version"] == "1.0"
    assert "private-token" not in response.text
    assert response.headers["Cache-Control"] == "no-store"


def test_domain_error_and_validation_body_are_safe(api):
    client, auth, _ = api
    auth.status.side_effect = AuthError("Log in again.", 401)
    response = client.get("/api/auth/kite/status")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "kite_auth_error"
    response = client.post(
        "/fixture/money",
        json={
            "amount": "private-token-body",
            "private-token-key": "private-token-value",
        },
    )
    assert response.status_code == 422
    assert "private-token" not in response.text
    assert "input" not in response.json()["error"]


def test_instrument_failures_share_the_error_contract(api):
    client, _, _ = api
    response = client.get("/api/market/instruments/status")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "instrument_error"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
