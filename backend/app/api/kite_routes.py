"""Browser login endpoints. Tokens are never returned to the browser."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.api.dashboard_routes import COOKIE as DASHBOARD_COOKIE
from app.api.dashboard_routes import DashboardSessions
from app.broker.kite_auth import KiteAuth, KiteStatus

COOKIE = "aurevon_kite_login"


def kite_router(auth: KiteAuth, sessions: DashboardSessions) -> APIRouter:
    router = APIRouter(prefix="/api/auth/kite", tags=["Kite authentication"])
    grants: dict[str, str] = {}

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
            if key not in auth.pending or not sessions.authenticated(grants[key]):
                grants.pop(key)
        if len(grants) >= 32:
            raise HTTPException(429)
        url, state = auth.begin_login()
        grants[state] = token or ""
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
        grant = grants.pop(request.query_params.get("state", ""), None)
        if not sessions.authenticated(grant):
            raise HTTPException(400)
        # Manual reads keep tokens out of validation error responses.
        auth.finish_login(
            request.query_params.get("state", ""),
            request.cookies.get(COOKIE, ""),
            request.query_params.get("request_token", ""),
            request.query_params.get("status", ""),
        )
        response = RedirectResponse("/api/auth/kite/status", status_code=303)
        response.delete_cookie(COOKIE, path="/api/auth/kite")
        return response

    return router
