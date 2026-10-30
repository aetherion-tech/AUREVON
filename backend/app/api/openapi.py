"""Publish WebSocket frames beside the REST schemas in the same v1 contract."""

from fastapi import FastAPI
from pydantic import TypeAdapter

from app.api.live_contracts import (
    EventBatch,
    HeartbeatFrame,
    ResyncFrame,
    SnapshotFrame,
)


def include_websocket_contract(app: FastAPI) -> None:
    original = app.openapi

    def schema() -> dict[str, object]:
        document = original()
        if "x-aurevon-websocket" not in document:
            frames = TypeAdapter(
                SnapshotFrame | EventBatch | ResyncFrame | HeartbeatFrame
            ).json_schema(
                mode="serialization", ref_template="#/components/schemas/{model}"
            )
            definitions = frames.pop("$defs", {})
            components = document.setdefault("components", {}).setdefault("schemas", {})
            for name, definition in definitions.items():
                if name in components and components[name] != definition:
                    # Input/serialization schemas may differ; transport models
                    # use the serialized version for both public schemas.
                    continue
                components[name] = definition
            components["WebSocketMessage"] = frames
            document["x-aurevon-websocket"] = {
                "path": "/ws/live",
                "cookie": "__Host-aurevon-dashboard",
                "origin_required": True,
                "message": {"$ref": "#/components/schemas/WebSocketMessage"},
                "resume": "run_id + after; apply only higher sequences in the same run",
                "resync": "discard local state; reload snapshot/history after resync",
                "slow_client": "bounded journal; close 1013 on overrun or send timeout",
                "auth_expired": "close 1008; authenticate again before reconnect",
            }
            schemes = document["components"].setdefault("securitySchemes", {})
            schemes["DashboardCookie"] = {
                "type": "apiKey",
                "in": "cookie",
                "name": "__Host-aurevon-dashboard",
            }
            schemes["CSRFToken"] = {
                "type": "apiKey",
                "in": "header",
                "name": "X-CSRF-Token",
            }
            schemes["ShadowIngress"] = {"type": "http", "scheme": "bearer"}
            for path, methods in document["paths"].items():
                for method, operation in methods.items():
                    if method not in ("get", "post", "put", "delete", "patch"):
                        continue
                    if path in (
                        "/api/health",
                        "/api/auth/dashboard/login",
                        "/api/auth/dashboard/status",
                    ):
                        continue
                    if path == "/api/shadow/tv-alert":
                        operation["security"] = [{"ShadowIngress": []}]
                        continue
                    if method != "get":
                        operation["security"] = [
                            {"DashboardCookie": [], "CSRFToken": []}
                        ]
                    elif (
                        path.startswith(
                            (
                                "/api/live/",
                                "/api/market/service/",
                                "/api/bricks",
                                "/api/candles",
                                "/api/alerts",
                                "/api/dev/",
                                "/api/mode",
                                "/api/shadow/",
                            )
                        )
                        or path == "/api/auth/kite/login"
                    ):
                        operation["security"] = [{"DashboardCookie": []}]
        return document

    app.openapi = schema  # type: ignore[method-assign]
