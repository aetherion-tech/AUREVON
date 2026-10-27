"""Paper-only mode contract. No arming or real-order adapter exists in this release."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import Contract
from app.api.security import DashboardSecurity


class ModeStatus(Contract):
    mode: Literal["PAPER"] = "PAPER"
    armed: Literal[False] = False
    live_orders_enabled: Literal[False] = False
    entries_enabled: Literal[False] = False
    arming_available: Literal[False] = False
    reason: Literal["execution_and_risk_not_implemented"] = (
        "execution_and_risk_not_implemented"
    )


class ModeRequest(Contract):
    mode: Literal["PAPER", "LIVE"]
    armed: bool = False
    confirm: str | None = None


def mode_router(security: DashboardSecurity) -> APIRouter:
    router = APIRouter(tags=["Paper mode"])

    @router.get("/api/mode", dependencies=[Depends(security.require)])
    def status() -> ModeStatus:
        return ModeStatus()

    @router.post("/api/mode")
    def update(body: ModeRequest) -> ModeStatus:
        if body.mode != "PAPER":
            raise HTTPException(403)
        if body.armed:
            raise HTTPException(409)
        return ModeStatus()

    return router
