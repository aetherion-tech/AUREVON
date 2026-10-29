"""Authenticated domain reads and audited idempotent PAPER actions."""

from collections.abc import Callable, Coroutine
from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.routing import APIRoute
from pydantic import BeforeValidator
from starlette.responses import Response

from app.api.domain_contracts import (
    ActionResult,
    DecisionView,
    LedgerView,
    MoneyAction,
    PnlSummary,
    PositionView,
    PrepareDecision,
    ResetAction,
    SettingsBundle,
    SettingsSchema,
    SettingsUpdate,
    SettingsView,
    SignalRecord,
    TradePage,
    WalletView,
)
from app.api.domain_service import DomainService, position_view, wallet_view
from app.api.schemas import Page, Pagination
from app.api.security import DashboardSecurity
from app.execution.models import PaperBook
from app.execution.service import ACTIVE
from app.strategy.models import Frozen, PlanDecision
from app.wallet.reporting import HistoryQuery, Period, bounds, summary, trades


def period_view(book: PaperBook, start: date, end: date) -> PnlSummary:
    from decimal import Decimal

    report = summary(book, start, end)
    selected = [
        t for t in trades(book) if start.isoformat() <= t["day"] <= end.isoformat()
    ]
    if selected:
        best = max(selected, key=lambda t: (Decimal(t["net"]), t["trade_id"]))
        worst = min(selected, key=lambda t: (Decimal(t["net"]), t["trade_id"]))
        report.update(
            best_trade_id=best["trade_id"],
            best_trade_net=best["net"],
            worst_trade_id=worst["trade_id"],
            worst_trade_net=worst["net"],
        )
    return PnlSummary.model_validate(report)


Key = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9:_-]+$",
    ),
]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]


def query_direction(value: Any) -> Any:
    return int(value) if isinstance(value, str) and value in {"1", "-1"} else value


def history_query(
    mode: Literal["PAPER"] = "PAPER",
    start: date | None = None,
    end: date | None = None,
    family: Literal["CO", "DIV", "OT"] | None = None,
    direction: Annotated[
        Literal[-1, 1] | None, BeforeValidator(query_direction)
    ] = None,
    grade: Annotated[int | None, Query(ge=1, le=3)] = None,
    result: Literal["WIN", "LOSS", "FLAT"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=2000)] = None,
    sort: Literal["closed_at", "net"] = "closed_at",
    order: Literal["asc", "desc"] = "asc",
) -> HistoryQuery:
    # HTTP query values arrive as strings; parse at the boundary, keeping the
    # internal accounting query's strict integer validation intact.
    if start is not None and end is not None and end < start:
        raise HTTPException(422)
    return HistoryQuery(
        mode=mode,
        start=start,
        end=end,
        family=family,
        direction=direction,
        grade=grade,
        result=result,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )


class EmptyAction(Frozen):
    pass


class DomainRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except KeyError:
                raise HTTPException(404) from None
            except ValueError:
                raise HTTPException(409) from None

        return handler


def domain_router(service: DomainService, security: DashboardSecurity) -> APIRouter:
    router = APIRouter(
        tags=["PAPER domain"],
        dependencies=[Depends(security.require)],
        route_class=DomainRoute,
    )

    @router.get("/api/signals")
    def signals(
        stream: Annotated[str, Query(min_length=1, max_length=160)],
        limit: Limit = 50,
        offset: Offset = 0,
        accepted: bool | None = None,
    ) -> Page[SignalRecord]:
        return service.signals(stream, limit, offset, accepted)

    @router.get("/api/decisions")
    def decisions(limit: Limit = 50, offset: Offset = 0) -> Page[DecisionView]:
        return service.decisions(limit, offset)

    @router.get("/api/decisions/{identity}")
    def decision_detail(identity: str) -> DecisionView:
        from sqlalchemy.orm import Session

        from app.db.models import DomainDecision

        with Session(service.engine) as db:
            row = db.get(DomainDecision, ("PAPER", identity))
            if row is None:
                raise HTTPException(404)
            return DecisionView.model_validate_json(row.payload)

    @router.post("/api/decisions/prepare")
    def prepare(body: PrepareDecision, key: Key) -> "PlanDecision":
        from app.strategy.models import PlanDecision

        return PlanDecision.model_validate_json(
            service.commands.run(
                key,
                "prepare",
                body.model_dump_json(),
                lambda: service.prepare(
                    body.stream, body.index, body.event_ordinal, key
                ).model_dump_json(),
            )
        )

    @router.post("/api/decisions/{identity}/confirm")
    def confirm(identity: str, key: Key, body: EmptyAction) -> ActionResult:
        return ActionResult.model_validate_json(
            service.commands.run(
                key,
                "confirm",
                identity,
                lambda: service.confirm(identity).model_dump_json(),
            )
        )

    @router.get("/api/positions/open")
    def positions(mode: Literal["PAPER"] = "PAPER") -> list[PositionView]:
        return [
            position_view(p)
            for p in service.execution().snapshot().positions.values()
            if p.status in ACTIVE
        ]

    @router.get(
        "/api/trades/export",
        response_class=Response,
        responses={
            200: {
                "description": "Filtered paper trade CSV",
                "content": {"text/csv": {"schema": {"type": "string"}}},
            }
        },
    )
    def export(query: Annotated[HistoryQuery, Depends(history_query)]) -> Response:
        content = service.wallet().export_csv(query)
        return Response(
            content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=paper-trades.csv"},
        )

    @router.get("/api/trades")
    def trades(query: Annotated[HistoryQuery, Depends(history_query)]) -> TradePage:
        return TradePage.model_validate(service.wallet().history(query))

    @router.get("/api/trades/{identity}")
    def trade_detail(identity: str, mode: Literal["PAPER"] = "PAPER") -> PositionView:
        return position_view(
            service.execution().snapshot().positions[identity], service.engine
        )

    @router.get("/api/wallet")
    def wallet(mode: Literal["PAPER"] = "PAPER") -> WalletView:
        return wallet_view(service.wallet())

    @router.get("/api/wallet/ledger")
    def ledger(
        limit: Limit = 50, offset: Offset = 0, mode: Literal["PAPER"] = "PAPER"
    ) -> Page[LedgerView]:
        b = service.wallet().snapshot()
        return Page(
            items=[
                LedgerView(sequence=i, **e.model_dump())
                for i, e in enumerate(b.ledger)
                if offset <= i < offset + limit
            ],
            pagination=Pagination(
                limit=limit,
                offset=offset,
                next_offset=offset + limit if len(b.ledger) > offset + limit else None,
            ),
        )

    def transfer(
        kind: str, key: str, body: MoneyAction | ResetAction | EmptyAction
    ) -> WalletView:
        def apply() -> str:
            wallet = service.wallet()
            at = service.market.clock()
            if kind == "initialize":
                wallet.initialize(at)
            elif isinstance(body, ResetAction):
                wallet.reset("api:" + key, body.amount, at)
            elif isinstance(body, MoneyAction):
                if kind == "deposit":
                    wallet.deposit("api:" + key, body.amount, at)
                else:
                    wallet.withdraw("api:" + key, body.amount, at)
            return wallet_view(wallet).model_dump_json()

        return WalletView.model_validate_json(
            service.commands.run(key, kind, body.model_dump_json(), apply)
        )

    @router.post("/api/wallet/initialize")
    def initialize(body: EmptyAction, key: Key) -> WalletView:
        return transfer("initialize", key, body)

    @router.post("/api/wallet/deposit")
    def deposit(body: MoneyAction, key: Key) -> WalletView:
        return transfer("deposit", key, body)

    @router.post("/api/wallet/withdraw")
    def withdraw(body: MoneyAction, key: Key) -> WalletView:
        return transfer("withdraw", key, body)

    @router.post("/api/wallet/reset")
    def reset(body: ResetAction, key: Key) -> WalletView:
        return transfer("reset", key, body)

    def report_dates(start: date | None, end: date | None) -> tuple[date, date]:
        today = service.market.clock().date()
        start, end = start or today - timedelta(days=30), end or today
        if end < start or (end - start).days > 366 or end > today:
            raise HTTPException(422)
        return start, end

    @router.get("/api/pnl/summary")
    def pnl(period: Period = "daily", mode: Literal["PAPER"] = "PAPER") -> PnlSummary:
        wallet = service.wallet()
        report = wallet.period(period, service.market.clock())
        return period_view(
            wallet.snapshot(),
            date.fromisoformat(report["start"]),
            date.fromisoformat(report["end"]),
        )

    @router.get("/api/pnl/daily")
    def daily(
        start: date | None = None,
        end: date | None = None,
        mode: Literal["PAPER"] = "PAPER",
    ) -> list[PnlSummary]:
        start, end = report_dates(start, end)
        book = service.wallet().snapshot()
        return [
            period_view(book, start + timedelta(days=i), start + timedelta(days=i))
            for i in range((end - start).days + 1)
        ]

    @router.get("/api/pnl/periods")
    def periods(
        period: Literal["weekly", "monthly"] = "monthly",
        count: Annotated[int, Query(ge=1, le=24)] = 6,
        mode: Literal["PAPER"] = "PAPER",
    ) -> list[PnlSummary]:
        book = service.wallet().snapshot()
        today = day = service.market.clock().date()
        records = []
        for _ in range(count):
            start, end = bounds(period, day, day)
            records.append(period_view(book, start, min(end, today)))
            day = start - timedelta(days=1)
        return records

    @router.get("/api/pnl/by-family")
    def families(
        start: date | None = None,
        end: date | None = None,
        mode: Literal["PAPER"] = "PAPER",
    ) -> PnlSummary:
        start, end = report_dates(start, end)
        return PnlSummary.model_validate(
            summary(service.wallet().snapshot(), start, end)
        )

    @router.get("/api/settings")
    def settings() -> SettingsView:
        view = service.settings.read()
        runtime = service.runtime_provider()
        return (
            view.model_copy(update={"activation": "active"})
            if runtime and runtime.settings == view
            else view
        )

    @router.get("/api/settings/defaults")
    def defaults() -> SettingsBundle:
        return service.settings.defaults

    @router.get("/api/settings/schema")
    def settings_schema() -> SettingsSchema:
        from app.indicator.settings import INPUTS

        return SettingsSchema.model_validate({"pine_inputs": INPUTS})

    @router.get("/api/settings/export")
    def settings_export() -> SettingsBundle:
        return service.settings.read().settings

    def update_settings(body: SettingsUpdate, key: str) -> SettingsView:
        def apply() -> str:
            prior = service.settings.read()
            changed = (
                prior.settings.model_copy(update={"display": body.settings.display})
                != body.settings
            )
            execution = service.execution_provider()
            if changed and (
                service.market.desired
                or service.market.worker is not None
                or (
                    execution is not None
                    and any(
                        p.status in ACTIVE
                        for p in execution.snapshot().positions.values()
                    )
                )
            ):
                raise HTTPException(409)
            return service.settings.update(body, key).model_dump_json()

        return SettingsView.model_validate_json(
            service.commands.run(key, "settings-update", body.model_dump_json(), apply)
        )

    @router.put("/api/settings")
    def settings_update(body: SettingsUpdate, key: Key) -> SettingsView:
        return update_settings(body, key)

    @router.post("/api/settings/import")
    def settings_import(body: SettingsUpdate, key: Key) -> SettingsView:
        return update_settings(body, key)

    @router.post("/api/settings/defaults")
    def restore_defaults(body: SettingsUpdate, key: Key) -> SettingsView:
        if body.settings != service.settings.defaults:
            raise HTTPException(422)
        return update_settings(body, key)

    return router
