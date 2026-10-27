"""Generated contract drift and production same-origin hosting checks."""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.tools.export_api import export


def test_export_is_deterministic_includes_ws_and_detects_drift(tmp_path):
    path = tmp_path / "openapi.json"
    export(path)
    first = path.read_bytes()
    export(path, check=True)
    export(path)
    assert path.read_bytes() == first
    schema = json.loads(first)
    assert "WebSocketMessage" in schema["components"]["schemas"]
    assert schema["paths"]["/api/dev/replay"]["post"]["security"] == [
        {"DashboardCookie": [], "CSRFToken": []}
    ]
    assert "security" not in schema["paths"]["/api/auth/dashboard/login"]["post"]
    assert schema["x-aurevon-websocket"]["origin_required"] is True
    path.write_text("{}")
    with pytest.raises(SystemExit, match="drift"):
        export(path, check=True)


def test_same_origin_static_dashboard_and_api(tmp_path):
    (tmp_path / "index.html").write_text("<main>Built dashboard fixture</main>")
    app = create_app(
        Settings(
            _env_file=None,
            database_url="sqlite://",
            dashboard_origins=[],
            dashboard_frontend_dir=tmp_path,
        )
    )
    client = TestClient(app)
    assert "Built dashboard fixture" in client.get("/dashboard/").text
    assert client.get("/api/health").status_code == 200
    assert client.get("/dashboard/../.env").status_code == 404


def test_cors_includes_auth_error_responses(tmp_path):
    from app.db.models import Base

    app = create_app(Settings(_env_file=None, database_url="sqlite://"))
    Base.metadata.create_all(app.state.database_engine)
    client = TestClient(app)
    response = client.post(
        "/api/market/service/stop", headers={"Origin": "https://localhost:5173"}
    )
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "https://localhost:5173"
