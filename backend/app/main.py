"""Application entry point. Run: uv run uvicorn app.main:app --reload."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.instrument_routes import instrument_router
from app.api.kite_routes import kite_router
from app.broker.instruments import InstrumentError, Instruments
from app.broker.kite_auth import AuthError, KiteAuth
from app.config import Settings
from app.db.session import database_engine
from app.logging_setup import configure_logging

log = structlog.get_logger("aurevon")


class HealthResponse(BaseModel):
    status: str = "ok"
    application: str
    mode: str = "PAPER"
    live_orders_enabled: bool = False


def create_app(
    settings: Settings | None = None, kite_auth: KiteAuth | None = None
) -> FastAPI:
    """Accept explicit settings so tests never need real broker credentials."""
    settings = settings if settings is not None else Settings()
    auth = kite_auth if kite_auth is not None else KiteAuth(settings)
    engine = database_engine(settings.database_url)
    instruments = Instruments(engine, auth)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        log.info(
            "application_started",
            application=settings.app_name,
            mode="PAPER",
            kite_configured=settings.kite_configured,
        )
        try:
            yield
        finally:
            auth.close()
            engine.dispose()
            log.info("application_stopped")

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Health, Kite login, and daily NIFTY instrument discovery.",
        lifespan=lifespan,
    )
    application.include_router(kite_router(auth))
    application.include_router(instrument_router(instruments))

    @application.exception_handler(InstrumentError)
    async def instrument_error(
        request: Request, error: InstrumentError
    ) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "instrument_error", "message": error.message}},
            status_code=error.status_code,
        )

    @application.exception_handler(AuthError)
    async def auth_error(request: Request, error: AuthError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "kite_auth_error", "message": error.message}},
            status_code=error.status_code,
        )

    @application.middleware("http")
    async def log_request(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = uuid4().hex
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Exception text and query strings can contain authentication tokens.
            log.error("request_failed", request_id=request_id, method=request.method)
            raise
        log.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            status_code=response.status_code,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @application.get("/", include_in_schema=False)
    def home() -> RedirectResponse:
        return RedirectResponse("/docs")

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(application=settings.app_name)

    return application


app = create_app()
