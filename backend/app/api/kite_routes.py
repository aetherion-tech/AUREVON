"""Browser login endpoints. Tokens are never returned to the browser."""

from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.api.dashboard_routes import COOKIE as DASHBOARD_COOKIE
from app.api.dashboard_routes import DashboardSessions
from app.broker.kite_auth import KiteAuth, KiteStatus

COOKIE = "aurevon_kite_login"


@dataclass(frozen=True)
class LoginGrant:
    session: str
    origin: str


def kite_router(auth: KiteAuth, sessions: DashboardSessions) -> APIRouter:
    router = APIRouter(prefix="/api/auth/kite", tags=["Kite authentication"])
    grants: dict[str, LoginGrant] = {}

    def browser_origin(request: Request) -> str:
        base = str(request.base_url).rstrip("/")
        # Vite terminates HTTPS and preserves Host while forwarding HTTP. Use
        # only a configured HTTPS origin with that exact host/port, never an
        # arbitrary forwarded header or user-provided redirect URL.
        for origin in auth.settings.dashboard_origins:
            if (
                urlsplit(origin).scheme == "https"
                and urlsplit(origin).netloc == request.url.netloc
            ):
                return origin
        return base

    @router.get("/status", response_model=KiteStatus)
    def status() -> KiteStatus:
        return auth.status()

    @router.get("/login", status_code=303, response_class=RedirectResponse)
    def login(request: Request) -> RedirectResponse:
        token = request.cookies.get(DASHBOARD_COOKIE)
        if not sessions.authenticated(token):
            raise HTTPException(401)
        # Keep a bounded delegation to the active dashboard session for the
        # cross-site OAuth return, where Strict dashboard cookies are absent.
        for key in list(grants):
            if key not in auth.pending or not sessions.authenticated(
                grants[key].session
            ):
                grants.pop(key)
        if len(grants) >= 32:
            raise HTTPException(429)
        url, state = auth.begin_login()
        grants[state] = LoginGrant(token or "", browser_origin(request))
        response = RedirectResponse(url, status_code=303)
        response.set_cookie(
            COOKIE,
            state,
            max_age=600,
            httponly=True,
            samesite="lax",
            path="/api/auth/kite",
        )
        return response

    @router.get("/callback", include_in_schema=False)
    def callback(request: Request) -> RedirectResponse:
        state = request.query_params.get("state", "")
        grant = grants.get(state)
        if grant is None or not sessions.authenticated(grant.session):
            raise HTTPException(400)
        if browser_origin(request) != grant.origin:
            # A configured broker callback can land on backend :8000 or the
            # other loopback hostname. Relay back to the originating dashboard
            # BEFORE checking its host-only cookie or consuming its one-time grant.
            # Only a server-retained authenticated origin is a redirect target.
            query = urlencode(
                {
                    key: request.query_params.get(key, "")
                    for key in ("state", "request_token", "status")
                }
            )
            return RedirectResponse(
                grant.origin + "/api/auth/kite/callback?" + query, status_code=303
            )
        # Manual reads keep tokens out of validation error responses.
        auth.finish_login(
            state,
            request.cookies.get(COOKIE, ""),
            request.query_params.get("request_token", ""),
            request.query_params.get("status", ""),
        )
        grants.pop(state, None)
        target = (
            "/dashboard/?kite=verified"
            if grant.origin in auth.settings.dashboard_origins
            or auth.settings.local_ui_enabled
            else "/api/auth/kite/status"
        )
        response = RedirectResponse(target, status_code=303)
        response.delete_cookie(COOKIE, path="/api/auth/kite")
        return response

    return router
