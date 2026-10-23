"""Use fake Kite HTTP responses; never authenticate a real broker account."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.broker.kite_auth import AuthError, KiteAuth, session_expiry
from app.config import BACKEND_DIR, Settings
from app.main import create_app


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        kite_api_key=SecretStr("fake-key"),
        kite_api_secret=SecretStr("fake-secret"),
        kite_session_file=tmp_path / "session.bin",
    )


def make_auth(settings: Settings, handler) -> KiteAuth:
    client = httpx.Client(
        base_url="https://api.kite.trade", transport=httpx.MockTransport(handler)
    )
    return KiteAuth(settings, client)


def login_state(client: TestClient) -> str:
    response = client.get("/api/auth/kite/login", follow_redirects=False)
    assert response.status_code == 303
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["api_key"] == ["fake-key"]
    assert "fake-secret" not in response.headers["location"]
    return parse_qs(query["redirect_params"][0])["state"][0]


def test_login_encrypts_session_restores_and_verifies_profile(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    def broker(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/session/token":
            form = parse_qs(request.content.decode())
            assert form["checksum"] == [
                hashlib.sha256(b"fake-keyone-time-tokenfake-secret").hexdigest()
            ]
            assert request.headers["X-Kite-Version"] == "3"
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "access_token": "private-access-token",
                        "user_id": "TEST123",
                    },
                },
            )
        assert request.url.path == "/user/profile"
        assert request.headers["Authorization"] == "token fake-key:private-access-token"
        return httpx.Response(
            200, json={"status": "success", "data": {"user_id": "TEST123"}}
        )

    auth = make_auth(settings, broker)
    with TestClient(create_app(settings, auth)) as client:
        state = login_state(client)
        query = urlencode(
            {"state": state, "request_token": "one-time-token", "status": "success"}
        )
        response = client.get(
            f"/api/auth/kite/callback?{query}", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/api/auth/kite/status"
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        status = client.get(response.headers["location"])
        assert status.json()["authenticated"] is True
        assert status.json()["user_id"] == "TEST123"
        assert "private-access-token" not in status.text
        assert client.get(f"/api/auth/kite/callback?{query}").status_code == 400

    encrypted = settings.kite_session_file.read_bytes()
    assert b"private-access-token" not in encrypted
    assert b"TEST123" not in encrypted
    restored = make_auth(settings, broker)
    try:
        assert restored.status().authenticated is True
    finally:
        restored.close()
    logs = (BACKEND_DIR / "logs" / "aurevon.log").read_text(encoding="utf-8")
    for secret in ("private-access-token", "one-time-token", "fake-secret", state):
        assert secret not in logs


@pytest.mark.parametrize(
    "scenario", ["missing_cookie", "wrong_state", "expired", "cancelled"]
)
def test_invalid_callback_never_contacts_broker(tmp_path: Path, scenario: str) -> None:
    settings = make_settings(tmp_path)

    def broker(request: httpx.Request) -> httpx.Response:
        pytest.fail("An invalid callback must never contact Kite")

    auth = make_auth(settings, broker)
    with TestClient(create_app(settings, auth)) as client:
        state = login_state(client)
        if scenario == "missing_cookie":
            client.cookies.clear()
        if scenario == "wrong_state":
            state = "unrecognised-state"
        if scenario == "expired":
            auth.pending[state] = datetime.now(UTC) - timedelta(seconds=1)
        response = client.get(
            "/api/auth/kite/callback",
            params={
                "state": state,
                "request_token": "sensitive-request-token",
                "status": "cancelled" if scenario == "cancelled" else "success",
            },
        )
        assert response.status_code == 400
        assert "sensitive-request-token" not in response.text
        assert not settings.kite_session_file.exists()


@pytest.mark.parametrize("failure", ["timeout", "rejected", "malformed"])
def test_exchange_failure_is_safe_and_does_not_save_session(
    tmp_path: Path, failure: str
) -> None:
    settings = make_settings(tmp_path)

    def broker(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("fake-secret", request=request)
        if failure == "malformed":
            return httpx.Response(200, content=b"not-json fake-secret")
        return httpx.Response(403, json={"status": "error", "message": "fake-secret"})

    auth = make_auth(settings, broker)
    with TestClient(create_app(settings, auth)) as client:
        state = login_state(client)
        response = client.get(
            "/api/auth/kite/callback",
            params={
                "state": state,
                "request_token": "one-time-token",
                "status": "success",
            },
        )
        assert response.status_code == 502
        assert "fake-secret" not in response.text
        assert not settings.kite_session_file.exists()


def test_expired_and_revoked_sessions_require_login(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    def broker(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"status": "error", "error_type": "TokenException"}
        )

    auth = make_auth(settings, broker)
    session = {
        "access_token": "test-token",
        "user_id": "TEST123",
        "api_key_hash": hashlib.sha256(b"fake-key").hexdigest(),
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    try:
        auth._save(session)
        assert auth.status().authenticated is False
        assert not settings.kite_session_file.exists()
        session["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        auth._save(session)
        assert auth.status().authenticated is False
        assert not settings.kite_session_file.exists()
    finally:
        auth.close()


def test_connection_failure_preserves_saved_session(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    def broker(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    auth = make_auth(settings, broker)
    try:
        auth._save(
            {
                "access_token": "test-token",
                "user_id": "TEST123",
                "api_key_hash": hashlib.sha256(b"fake-key").hexdigest(),
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            }
        )
        with pytest.raises(AuthError, match="Cannot reach Kite"):
            auth.status()
        assert settings.kite_session_file.exists()
    finally:
        auth.close()


@pytest.mark.parametrize("hour, expected_day", [(0, 23), (5, 23), (6, 24), (12, 24)])
def test_expiry_uses_next_six_am_ist(hour: int, expected_day: int) -> None:
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 10, 23, hour, tzinfo=ist)
    assert session_expiry(now).astimezone(ist) == datetime(
        2026, 10, expected_day, 6, tzinfo=ist
    )
