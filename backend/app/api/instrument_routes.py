"""Read cached contracts and explicitly refresh the daily instrument snapshot."""

from datetime import date
from typing import Any

from fastapi import APIRouter

from app.broker.instruments import Instruments


def instrument_router(service: Instruments) -> APIRouter:
    router = APIRouter(prefix="/api/market", tags=["Market instruments"])

    @router.get("/instruments/status")
    def status() -> dict[str, Any]:
        return service.status()

    @router.post("/instruments/refresh")
    def refresh() -> dict[str, Any]:
        return service.refresh()

    @router.get("/nifty")
    def nifty(expiry: date | None = None) -> dict[str, Any]:
        return service.nifty(expiry)

    return router
