"""Shared cookie/origin/CSRF policy and payload-free persistent mutation audit."""

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, Request, WebSocket
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.routing import compile_path

from app.api.dashboard_routes import COOKIE, DashboardSessions
from app.broker.kite_auth import IST
from app.config import Settings
from app.db.models import AuditEntry


class DashboardSecurity:
    def __init__(
        self, settings: Settings, engine: Engine, sessions: DashboardSessions
    ) -> None:
        self.settings, self.engine, self.sessions = settings, engine, sessions

    def origin_allowed(self, origin: str | None, base: str) -> bool:
        return origin is not None and origin in [base, *self.settings.dashboard_origins]

    def require(self, request: Request) -> None:
        if not self.sessions.authenticated(request.cookies.get(COOKIE)):
            raise HTTPException(401)

    def authorize(self, request: Request) -> None:
        path = request.url.path
        if path == "/api/auth/dashboard/login":
            origin = request.headers.get("origin")
            if (
                origin is not None
                and not self.origin_allowed(origin, str(request.base_url).rstrip("/"))
            ) or (request.headers.get("sec-fetch-site") == "cross-site"):
                raise HTTPException(403)
            if (
                request.headers.get("content-type", "").split(";")[0]
                != "application/json"
            ):
                raise HTTPException(415)
            return
        # OAuth callback is authorized by the random one-time state + Lax cookie
        # established by an authenticated login initiation. Strict dashboard cookie
        # is not sent by browsers on the cross-site return from the broker.
        if path == "/api/auth/kite/callback":
            return
        self.require(request)
        origin = request.headers.get("origin")
        if origin is not None and not self.origin_allowed(
            origin, str(request.base_url).rstrip("/")
        ):
            raise HTTPException(403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not self.sessions.check_csrf(
                request.cookies.get(COOKIE), request.headers.get("x-csrf-token")
            ):
                raise HTTPException(403)

    def websocket_allowed(self, socket: WebSocket) -> bool:
        base = str(socket.base_url).rstrip("/")
        base = base.replace("wss://", "https://", 1).replace("ws://", "http://", 1)
        return self.origin_allowed(
            socket.headers.get("origin"), base
        ) and self.sessions.authenticated(socket.cookies.get(COOKIE))

    def begin_audit(self, request: Request) -> str:
        # Use a matched route template, never request paths/queries/bodies/headers.
        action = "unrecognized_api_mutation"
        for path, methods in request.app.openapi()["paths"].items():
            if request.method.lower() in methods and compile_path(path)[0].fullmatch(
                request.url.path
            ):
                action = request.method + " " + path
                break
        if request.url.path == "/api/auth/kite/callback":
            action = "GET /api/auth/kite/callback"
        identity = uuid4().hex
        with Session(self.engine) as db, db.begin():
            db.add(
                AuditEntry(
                    id=identity,
                    at=datetime.now(IST).isoformat(),
                    action=action,
                    actor="dashboard"
                    if self.sessions.authenticated(request.cookies.get(COOKIE))
                    else "unauthenticated",
                    status=None,
                    request_id=request.state.request_id,
                )
            )
        return identity

    def finish_audit(self, identity: str, status: int) -> None:
        with Session(self.engine) as db, db.begin():
            row = db.get(AuditEntry, identity)
            if row is None:
                raise RuntimeError("Missing mutation audit intent")
            row.status = status
