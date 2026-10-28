"""Application entry point. Run: uv run uvicorn app.main:app --reload."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, suppress
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.dashboard_routes import DashboardSessions, dashboard_router
from app.api.event_hub import EventHub
from app.api.instrument_routes import instrument_router
from app.api.kite_routes import kite_router
from app.api.live_routes import live_router
from app.api.live_service import LiveService
from app.api.mode_routes import mode_router
from app.api.openapi import include_websocket_contract
from app.api.replay_routes import ReplayService, replay_router
from app.api.schemas import (
    API_VERSION,
    APIError,
    ErrorDetail,
    ErrorEnvelope,
    HealthResponse,
)
from app.api.security import DashboardSecurity
from app.api.strategy_routes import strategy_router
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
    sessions = DashboardSessions(settings, engine)
    security = DashboardSecurity(settings, engine, sessions)
    hub = EventHub()
    live = LiveService(market, engine, hub)
    replay = ReplayService(settings, market)

    async def publish_market() -> None:
        while True:
            try:
                live.sample()
            except Exception:
                # Storage failures surface to callers; never emit healthy fiction.
                pass
            await asyncio.sleep(0.25)

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
        publisher = asyncio.create_task(publish_market())
        try:
            yield
        finally:
            try:
                publisher.cancel()
                with suppress(asyncio.CancelledError):
                    await publisher
                await replay.close()
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
            for status in (
                400,
                401,
                403,
                404,
                405,
                409,
                413,
                415,
                422,
                429,
                500,
                502,
                503,
            )
        },
    )
    application.state.market_service = market
    application.state.dashboard_sessions = sessions
    application.state.dashboard_security = security
    application.state.database_engine = engine
    application.state.live_service = live
    application.state.event_hub = hub
    application.state.replay_service = replay
    application.include_router(dashboard_router(settings, sessions))
    application.include_router(kite_router(auth, sessions))
    application.include_router(instrument_router(instruments))
    application.include_router(live_router(live, security))
    application.include_router(replay_router(replay, security))
    application.include_router(mode_router(security))
    application.include_router(strategy_router(market))

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
        audit_id: str | None = None
        try:
            guarded = (
                request.url.path.startswith("/api/")
                and request.url.path != "/api/health"
                and (
                    request.method not in ("GET", "HEAD", "OPTIONS")
                    or request.url.path
                    in ("/api/auth/kite/login", "/api/auth/kite/callback")
                )
            )
            if guarded:
                # No mutation may begin without a committed audit intent.
                audit_id = security.begin_audit(request)
                security.authorize(request)
            response = await call_next(request)
        except HTTPException as error:
            response = error_response(
                request,
                "http_error",
                "Access denied.",
                error.status_code,
                headers=error.headers,
            )
        except SQLAlchemyError:
            response = error_response(
                request,
                "storage_unavailable",
                "Required dashboard storage is unavailable.",
                503,
            )
        except Exception:
            # Exception text and query strings can contain authentication tokens.
            log.error("request_failed", request_id=request_id, method=request.method)
            response = error_response(
                request, "internal_error", "Internal server error.", 500
            )
        if audit_id is not None:
            try:
                security.finish_audit(audit_id, response.status_code)
            except Exception:
                response = error_response(
                    request,
                    "audit_unavailable",
                    "Audit completion unavailable; inspect pending audit before retry.",
                    503,
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

    if settings.dashboard_frontend_dir is not None:
        root = settings.dashboard_frontend_dir.resolve(strict=True)
        if not (root / "index.html").is_file():
            raise ValueError("Dashboard build must contain index.html")
        application.mount(
            "/dashboard", StaticFiles(directory=root, html=True), name="dashboard"
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.dashboard_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
        expose_headers=["X-CSRF-Token", "X-Request-ID", "X-AUREVON-API-Version"],
    )

    include_websocket_contract(application)
    return application


app = create_app()
