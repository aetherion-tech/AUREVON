"""Browser login endpoints. Tokens are never returned to the browser."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.broker.kite_auth import KiteAuth, KiteStatus

COOKIE = "aurevon_kite_login"


def kite_router(auth: KiteAuth) -> APIRouter:
    router = APIRouter(prefix="/api/auth/kite", tags=["Kite authentication"])

    @router.get("/status", response_model=KiteStatus)
    def status() -> KiteStatus:
        return auth.status()

    @router.get("/login", status_code=303, response_class=RedirectResponse)
    def login() -> RedirectResponse:
        url, state = auth.begin_login()
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
