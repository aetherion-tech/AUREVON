"""Check startup without credentials and keep secrets out of HTTP responses/logs."""

from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import BACKEND_DIR, Settings
from app.main import create_app


def test_health_without_kite_credentials(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        kite_api_key=SecretStr(""),
        kite_api_secret=SecretStr(""),
        kite_session_file=tmp_path / "session.bin",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "application": "AUREVON",
            "mode": "PAPER",
            "live_orders_enabled": False,
        }
        assert response.headers["X-Request-ID"]
        assert client.get("/api/auth/kite/status").json()["configured"] is False


def test_configuration_is_not_authentication_and_secrets_stay_private(
    tmp_path: Path,
) -> None:
    api_key = "test-key-must-stay-private"
    api_secret = "test-secret-must-stay-private"
    settings = Settings(
        _env_file=None,
        kite_api_key=SecretStr(api_key),
        kite_api_secret=SecretStr(api_secret),
        kite_session_file=tmp_path / "session.bin",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/auth/kite/status?request_token=private-query-token")
        assert response.json()["configured"] is True
        assert response.json()["authenticated"] is False
        assert api_key not in response.text
        assert api_secret not in response.text
    logs = (BACKEND_DIR / "logs" / "aurevon.log").read_text(encoding="utf-8")
    assert "application_started" in logs
    assert "request_completed" in logs
    assert "application_stopped" in logs
    assert api_key not in logs
    assert api_secret not in logs
    assert "private-query-token" not in logs


def test_env_file_loading(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_NAME=AUREVON Test\nLOG_LEVEL=WARNING\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.app_name == "AUREVON Test"
    assert settings.log_level == "WARNING"
