"""Read cached contracts and explicitly refresh the daily instrument snapshot."""

from typing import Any

from fastapi import APIRouter

from app.api.schemas import ExchangeDate, InstrumentStatus, NiftyResponse
from app.broker.instruments import Instruments


def instrument_router(service: Instruments) -> APIRouter:
    router = APIRouter(prefix="/api/market", tags=["Market instruments"])

    @router.get("/instruments/status", response_model=InstrumentStatus)
    def status() -> dict[str, Any]:
        return service.status()

    @router.post("/instruments/refresh", response_model=InstrumentStatus)
    def refresh() -> dict[str, Any]:
        return service.refresh()

    @router.get("/nifty", response_model=NiftyResponse)
    def nifty(expiry: ExchangeDate | None = None) -> dict[str, Any]:
        return service.nifty(expiry)

    return router
