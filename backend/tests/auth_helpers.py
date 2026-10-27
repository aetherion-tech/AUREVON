"""Explicit dashboard authentication for existing fake-broker integration tests."""

from functools import lru_cache

from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.api.dashboard_routes import COOKIE
from app.db.models import Base


@lru_cache
def password_hash() -> str:
    return PasswordHasher().hash("fixture-password-only")


def authenticate(client: TestClient) -> None:
    Base.metadata.create_all(client.app.state.database_engine)  # type: ignore[union-attr]
    client.base_url = "https://testserver"
    response = client.post(
        "/api/auth/dashboard/login", json={"password": "fixture-password-only"}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.headers["X-CSRF-Token"]
    assert client.cookies.get(COOKIE)
