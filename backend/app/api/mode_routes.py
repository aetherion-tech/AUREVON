"""Paper-only mode contract. No arming or real-order adapter exists in this release."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from app.api.domain_service import DomainService
from app.api.schemas import Contract
from app.api.security import DashboardSecurity


class ModeStatus(Contract):
    mode: Literal["PAPER"] = "PAPER"
    armed: Literal[False] = False
    live_orders_enabled: Literal[False] = False
    entries_enabled: bool = False
    arming_available: Literal[False] = False
    reason: Literal["paper_execution_not_activated", "paper_owner_attached"] = (
        "paper_execution_not_activated"
    )


class ModeRequest(Contract):
    mode: Literal["PAPER", "LIVE"]
    armed: bool = False
    confirm: str | None = None


def mode_router(
    security: DashboardSecurity, domain: DomainService | None = None
) -> APIRouter:
    router = APIRouter(tags=["Paper mode"])

    @router.get("/api/mode", dependencies=[Depends(security.require)])
    def status() -> ModeStatus:
        return ModeStatus(
            entries_enabled=domain.entries_enabled() if domain else False,
            reason="paper_owner_attached"
            if domain and domain.execution_provider() is not None
            else "paper_execution_not_activated",
        )

    @router.post("/api/mode")
    def update(body: ModeRequest) -> ModeStatus:
        if body.mode != "PAPER":
            raise HTTPException(403)
        if body.armed:
            raise HTTPException(409)
        return status()

    return router
