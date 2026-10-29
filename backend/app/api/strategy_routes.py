"""Authenticated preview only: candidate data and estimates never execute orders."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import Field, StrictBool
from sqlalchemy.exc import SQLAlchemyError

from app.api.domain_storage import SettingsStore
from app.market.exchange_calendar import CalendarError
from app.market.service import MarketService, blocking
from app.strategy.models import (
    CapitalSnapshot,
    Frozen,
    Nonnegative,
    PlanDecision,
    SignalInput,
    StrategySettings,
)
from app.strategy.planner import PlanRejected, build_plan
from app.strategy.service import load_catalog, preview, save_decision


class ReadOnlyPreview(Frozen):
    signal: SignalInput
    free_capital: Nonnegative | None = None


class StrikePreview(Frozen):
    signal: SignalInput
    settings: StrategySettings = Field(default_factory=StrategySettings)
    free_capital: Nonnegative | None = None
    subscribe_quotes: StrictBool = False


def strategy_router(
    market: MarketService, settings_store: SettingsStore | None = None
) -> APIRouter:
    router = APIRouter(tags=["Nonexecuting strategy preview"])

    @router.post("/api/strikes/preview")
    async def readonly_preview(body: ReadOnlyPreview) -> PlanDecision:
        now = market.clock()
        settings = (
            settings_store.read().settings.strategy
            if settings_store
            else StrategySettings()
        )
        try:
            calendar = market.calendar.year(now.year)
            catalog = await blocking(lambda: load_catalog(market.engine, now))
            async with market.lock:
                worker = market.worker
                quotes = (
                    worker.option_quotes.snapshot()
                    if worker
                    and worker.running
                    and worker.connected
                    and worker._history_ready.is_set()
                    and not worker.gap_required
                    else {}
                )
            capital = (
                CapitalSnapshot(
                    at=now,
                    free_capital=body.free_capital,
                    source="USER_PREVIEW",
                    revision="request-only",
                )
                if body.free_capital is not None
                else None
            )
            return build_plan(
                body.signal, catalog, quotes, capital, now, calendar, settings
            )
        except (PlanRejected, CalendarError) as error:
            return PlanDecision(
                accepted=False,
                reason=str(error)
                if isinstance(error, PlanRejected)
                else "calendar_unavailable",
            )

    @router.post("/api/settings/preview-strikes")
    async def preview_strikes(body: StrikePreview) -> PlanDecision:
        # Shared API middleware enforces login, origin, CSRF and durable audit.
        now = market.clock()
        quotes = {}
        try:
            calendar = market.calendar.year(now.year)
            catalog = await blocking(lambda: load_catalog(market.engine, now))
            discovered = build_plan(
                body.signal,
                catalog,
                {},
                None,
                now,
                calendar,
                body.settings,
                discover=True,
            )
            if discovered.reason != "quotes_required":
                return await blocking(
                    lambda: save_decision(
                        market.engine, discovered, body.signal, body.settings, now
                    )
                )
            async with market.lock:
                worker = market.worker
                if (
                    worker is not None
                    and worker.running
                    and worker.connected
                    and worker._history_ready.is_set()
                    and not worker.gap_required
                ):
                    if body.subscribe_quotes:
                        try:
                            await worker.set_option_contracts(
                                list(discovered.candidates)
                            )
                        except (RuntimeError, ValueError, TimeoutError):
                            failed = PlanDecision(
                                accepted=False,
                                reason="option_subscription_unavailable",
                                candidates=discovered.candidates,
                            )
                            return await blocking(
                                lambda: save_decision(
                                    market.engine,
                                    failed,
                                    body.signal,
                                    body.settings,
                                    now,
                                )
                            )
                    quotes = worker.option_quotes.snapshot()
            capital = (
                CapitalSnapshot(
                    at=now,
                    free_capital=Decimal(body.free_capital),
                    source="USER_PREVIEW",
                    revision="request-only",
                )
                if body.free_capital is not None
                else None
            )
            now = market.clock()
            return await blocking(
                lambda: preview(
                    market.engine,
                    body.signal,
                    catalog,
                    quotes,
                    capital,
                    now,
                    calendar,
                    body.settings,
                )
            )
        except (PlanRejected, CalendarError) as error:
            reason = (
                str(error)
                if isinstance(error, PlanRejected)
                else "calendar_unavailable"
            )
            try:
                return await blocking(
                    lambda: save_decision(
                        market.engine,
                        PlanDecision(accepted=False, reason=reason),
                        body.signal,
                        body.settings,
                        now,
                    )
                )
            except SQLAlchemyError:
                raise HTTPException(503) from None
        except SQLAlchemyError:
            raise HTTPException(503) from None

    return router
