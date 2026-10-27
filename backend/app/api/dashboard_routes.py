"""Single-operator dashboard sessions; independent of broker credentials."""

import secrets
from datetime import datetime
from threading import Lock
from time import time

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field, SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api.schemas import Contract
from app.broker.kite_auth import IST
from app.config import Settings
from app.db.models import DashboardSecurityState

COOKIE = "__Host-aurevon-dashboard"


class DashboardLogin(Contract):
    password: SecretStr = Field(min_length=1, max_length=1024)


class DashboardStatus(Contract):
    configured: bool
    authenticated: bool


class DashboardSessions:
    """One active session, revoked on logout, replacement login or process restart."""

    def __init__(self, settings: Settings, engine: Engine | None = None) -> None:
        self._hash = settings.dashboard_password_hash.get_secret_value()
        self._ttl = settings.dashboard_session_seconds
        self._key = secrets.token_bytes(32)
        self._active: str | None = None
        self._expires = 0.0
        self._lock = Lock()
        self._hasher = PasswordHasher()
        self._engine = engine
        self._lockout_seconds = settings.dashboard_lockout_seconds
        self._failures = 0
        self._locked_until = 0.0
        self._csrf = secrets.token_urlsafe(32)
        if self._hash:
            # Fail closed on malformed configuration without including the hash.
            try:
                from argon2 import extract_parameters

                extract_parameters(self._hash)
            except InvalidHashError:
                raise ValueError("Invalid dashboard Argon2 password hash") from None

    @property
    def configured(self) -> bool:
        return bool(self._hash)

    def login(self, password: str) -> str:
        if not self.configured:
            raise HTTPException(503)
        with self._lock:
            now = time()
            if self._engine is not None:
                with Session(self._engine) as db:
                    state = db.get(DashboardSecurityState, "operator")
                    if state:
                        self._failures = state.failures
                        self._locked_until = (
                            datetime.fromisoformat(state.locked_until).timestamp()
                            if state.locked_until
                            else 0.0
                        )
            if now < self._locked_until:
                raise HTTPException(
                    429,
                    headers={
                        "Retry-After": str(max(1, int(self._locked_until - now) + 1))
                    },
                )
            if self._locked_until:
                self._failures = 0
                self._locked_until = 0.0
            try:
                self._hasher.verify(self._hash, password)
            except (VerificationError, InvalidHashError):
                self._failures += 1
                if self._failures >= 5:
                    self._locked_until = now + self._lockout_seconds
                self._persist_failures()
                if self._locked_until:
                    raise HTTPException(
                        429, headers={"Retry-After": str(self._lockout_seconds)}
                    ) from None
                raise HTTPException(401) from None
            self._failures = 0
            self._locked_until = 0.0
            self._persist_failures()
            now = int(time())
            self._csrf = secrets.token_urlsafe(32)
            self._active = secrets.token_urlsafe(32)
            self._expires = now + self._ttl
            return jwt.encode(
                {
                    "sub": "dashboard",
                    "aud": "aurevon-dashboard",
                    "iat": now,
                    "exp": int(self._expires),
                    "jti": self._active,
                },
                self._key,
                algorithm="HS256",
            )

    def _persist_failures(self) -> None:
        if self._engine is not None:
            with Session(self._engine) as db, db.begin():
                db.merge(
                    DashboardSecurityState(
                        key="operator",
                        failures=self._failures,
                        locked_until=datetime.fromtimestamp(
                            self._locked_until, IST
                        ).isoformat()
                        if self._locked_until
                        else None,
                    )
                )

    def csrf(self, token: str | None) -> str | None:
        return self._csrf if self.authenticated(token) else None

    def check_csrf(self, token: str | None, supplied: str | None) -> bool:
        expected = self.csrf(token)
        return bool(
            expected and supplied and secrets.compare_digest(expected, supplied)
        )

    def authenticated(self, token: str | None) -> bool:
        if not token or len(token) > 4096:
            return False
        try:
            claims = jwt.decode(
                token,
                self._key,
                algorithms=["HS256"],
                audience="aurevon-dashboard",
                options={"require": ["sub", "aud", "iat", "exp", "jti"]},
            )
        except jwt.InvalidTokenError:
            return False
        with self._lock:
            return (
                claims["sub"] == "dashboard"
                and self._active is not None
                and claims["jti"] == self._active
                and time() < self._expires
            )

    def logout(self, token: str | None) -> None:
        # Match under the same lock as revocation; stale clients cannot revoke a
        # replacement login. Untrusted tokens never select another user's state.
        with self._lock:
            if token:
                try:
                    claims = jwt.decode(
                        token,
                        self._key,
                        algorithms=["HS256"],
                        audience="aurevon-dashboard",
                    )
                except jwt.InvalidTokenError:
                    return
                if claims.get("jti") == self._active:
                    self._active = None


def dashboard_router(settings: Settings, sessions: DashboardSessions) -> APIRouter:
    router = APIRouter(prefix="/api/auth/dashboard", tags=["Dashboard authentication"])

    def same_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        allowed = [str(request.base_url).rstrip("/"), *settings.dashboard_origins]
        if origin is not None and origin not in allowed:
            raise HTTPException(403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403)

    @router.get("/status")
    def status(request: Request, response: Response) -> DashboardStatus:
        csrf = sessions.csrf(request.cookies.get(COOKIE))
        if csrf:
            response.headers["X-CSRF-Token"] = csrf
        return DashboardStatus(
            configured=sessions.configured,
            authenticated=sessions.authenticated(request.cookies.get(COOKIE)),
        )

    @router.post("/login")
    def login(
        body: DashboardLogin, request: Request, response: Response
    ) -> DashboardStatus:
        same_origin(request)
        token = sessions.login(body.password.get_secret_value())
        response.headers["X-CSRF-Token"] = sessions.csrf(token) or ""
        response.set_cookie(
            COOKIE,
            token,
            max_age=settings.dashboard_session_seconds,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return DashboardStatus(configured=True, authenticated=True)

    @router.post("/logout")
    def logout(request: Request, response: Response) -> DashboardStatus:
        same_origin(request)
        sessions.logout(request.cookies.get(COOKIE))
        response.delete_cookie(
            COOKIE, secure=True, httponly=True, samesite="strict", path="/"
        )
        return DashboardStatus(configured=sessions.configured, authenticated=False)

    return router
