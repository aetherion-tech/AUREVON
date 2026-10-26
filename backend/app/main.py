"""Application entry point. Run: uv run uvicorn app.main:app --reload."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.instrument_routes import instrument_router
from app.api.kite_routes import kite_router
from app.api.schemas import (
    API_VERSION,
    APIError,
    ErrorDetail,
    ErrorEnvelope,
    HealthResponse,
)
from app.broker.instruments import InstrumentError, Instruments
from app.broker.kite_auth import AuthError, KiteAuth
from app.config import Settings
from app.db.session import database_engine
from app.logging_setup import configure_logging
from app.market.service import MarketService

log = structlog.get_logger("aurevon")


def create_app(
    settings: Settings | None = None, kite_auth: KiteAuth | None = None
) -> FastAPI:
    """Accept explicit settings so tests never need real broker credentials."""
    settings = settings if settings is not None else Settings()
    auth = kite_auth if kite_auth is not None else KiteAuth(settings)
    engine = database_engine(settings.database_url)
    instruments = Instruments(engine, auth)
    market = MarketService(settings, auth, engine, instruments)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        log.info(
            "application_started",
            application=settings.app_name,
            mode="PAPER",
            kite_configured=settings.kite_configured,
        )
        await market.open()
        try:
            yield
        finally:
            try:
                await market.close()
            finally:
                auth.close()
                engine.dispose()
            log.info("application_stopped")

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Health, Kite login, and daily NIFTY instrument discovery.",
        lifespan=lifespan,
        responses={
            status: {"model": ErrorEnvelope}
            for status in (400, 401, 403, 404, 405, 409, 422, 429, 500, 502, 503)
        },
    )
    application.state.market_service = market
    application.include_router(kite_router(auth))
    application.include_router(instrument_router(instruments))

    def error_response(
        request: Request,
        code: str,
        message: str,
        status: int,
        details: list[ErrorDetail] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> JSONResponse:
        body = ErrorEnvelope(
            error=APIError(
                code=code,
                message=message,
                request_id=getattr(request.state, "request_id", None),
                details=details or [],
            )
        )
        return JSONResponse(
            body.model_dump(mode="json"), status_code=status, headers=headers
        )

    @application.exception_handler(InstrumentError)
    async def instrument_error(
        request: Request, error: InstrumentError
    ) -> JSONResponse:
        return error_response(
            request, "instrument_error", error.message, error.status_code
        )

    @application.exception_handler(AuthError)
    async def auth_error(request: Request, error: AuthError) -> JSONResponse:
        return error_response(
            request, "kite_auth_error", error.message, error.status_code
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # Do not return input, ctx or raw messages: they can contain secrets.
        details = [
            ErrorDetail(
                location=[
                    item
                    if isinstance(item, int)
                    else ("field" if entry["type"] == "extra_forbidden" else str(item))
                    for item in entry["loc"]
                ],
                code=entry["type"],
            )
            for entry in error.errors()
        ]
        return error_response(
            request, "validation_error", "Request validation failed.", 422, details
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        from http import HTTPStatus

        try:
            message = HTTPStatus(error.status_code).phrase
        except ValueError:
            message = "HTTP request failed."
        return error_response(
            request, "http_error", message, error.status_code, headers=error.headers
        )

    @application.middleware("http")
    async def log_request(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Exception text and query strings can contain authentication tokens.
            log.error("request_failed", request_id=request_id, method=request.method)
            response = error_response(
                request, "internal_error", "Internal server error.", 500
            )
        log.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            status_code=response.status_code,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        response.headers["X-AUREVON-API-Version"] = API_VERSION
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
