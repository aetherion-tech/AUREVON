"""Dashboard credentials and revoked cookies never authenticate as Kite."""

from unittest.mock import patch

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dashboard_routes import COOKIE, DashboardSessions
from app.config import Settings
from app.db.models import Base
from app.main import create_app as make_app


def create_app(config):
    app = make_app(config)
    Base.metadata.create_all(app.state.database_engine)
    return app


@pytest.fixture(scope="module")
def password_hash():
    return PasswordHasher().hash("test-only-password")


def settings(password_hash=""):
    return Settings(
        _env_file=None,
        dashboard_password_hash=SecretStr(password_hash),
        database_url="sqlite://",
        market_service_enabled=False,
    )


def test_cookie_lifecycle_and_kite_separation(password_hash):
    client = TestClient(
        create_app(settings(password_hash)), base_url="https://testserver"
    )
    assert client.get("/api/auth/dashboard/status").json() == {
        "configured": True,
        "authenticated": False,
    }
    bad = client.post("/api/auth/dashboard/login", json={"password": "wrong"})
    assert bad.status_code == 401
    assert "wrong" not in bad.text
    response = client.post(
        "/api/auth/dashboard/login", json={"password": "test-only-password"}
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/", "Max-Age=28800"):
        assert flag in cookie
    client.headers["X-CSRF-Token"] = response.headers["X-CSRF-Token"]
    old = client.cookies.get(COOKIE)
    assert client.get("/api/auth/dashboard/status").json()["authenticated"]
    rotated = client.post(
        "/api/auth/dashboard/login", json={"password": "test-only-password"}
    )
    client.headers["X-CSRF-Token"] = rotated.headers["X-CSRF-Token"]
    current = client.cookies.get(COOKIE)
    assert old != current
    other = TestClient(client.app, base_url="https://testserver")
    other.cookies.set(COOKIE, old)
    assert not other.get("/api/auth/dashboard/status").json()["authenticated"]
    other.post("/api/auth/dashboard/logout")
    assert client.get("/api/auth/dashboard/status").json()["authenticated"]
    logout = client.post("/api/auth/dashboard/logout")
    assert logout.status_code == 200
    other.cookies.set(COOKIE, current)
    assert not other.get("/api/auth/dashboard/status").json()["authenticated"]
    assert "Max-Age=0" in logout.headers["set-cookie"]


def test_disabled_configuration():
    client = TestClient(create_app(settings()), base_url="https://testserver")
    assert client.get("/api/auth/dashboard/status").json() == {
        "configured": False,
        "authenticated": False,
    }
    assert (
        client.post(
            "/api/auth/dashboard/login", json={"password": "anything"}
        ).status_code
        == 503
    )


@pytest.mark.parametrize("token", [None, "broken", "x" * 4097])
def test_invalid_tokens(password_hash, token):
    assert not DashboardSessions(settings(password_hash)).authenticated(token)


def test_expiry_tamper_and_restart(password_hash):
    config = settings(password_hash)
    sessions = DashboardSessions(config)
    token = sessions.login("test-only-password")
    assert sessions.authenticated(token)
    assert not sessions.authenticated(token[:-10] + "AAAAAAAAAA")
    assert not DashboardSessions(config).authenticated(token)
    with patch("app.api.dashboard_routes.time", return_value=10**11):
        assert not sessions.authenticated(token)


@pytest.mark.parametrize("path", ["login", "logout"])
def test_cross_origin_rejected(password_hash, path):
    client = TestClient(
        create_app(settings(password_hash)), base_url="https://testserver"
    )
    response = client.post(
        "/api/auth/dashboard/" + path,
        headers={"Origin": "https://evil.example"},
        json={"password": "test-only-password"},
    )
    assert response.status_code in (401, 403)
    assert "set-cookie" not in response.headers


def test_malformed_configuration_does_not_expose_hash():
    with pytest.raises(ValueError, match="Invalid dashboard Argon2 password hash"):
        DashboardSessions(settings("private-invalid-value"))


def test_password_validation_redacts_input(password_hash):
    client = TestClient(create_app(settings(password_hash)))
    response = client.post("/api/auth/dashboard/login", json={"password": "x" * 1025})
    assert response.status_code == 422
    assert "xxx" not in response.text
