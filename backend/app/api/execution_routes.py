"""Paper control hooks; an executor must be explicitly attached by its owner.

No executor is attached on normal application startup before G1/G2/G3 acceptance.
Never accept caller-supplied quotes, clocks or readiness through these routes.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.domain_service import DomainService
from app.execution.models import PositionStatus
from app.execution.service import PaperExecution
from app.market.renko_builder import IST
from app.strategy.models import Frozen


class ExecutionControl(Frozen):
    mode: Literal["PAPER"] = "PAPER"
    armed: Literal[False] = False
    entries_locked: bool
    pending_closures: int


def execution_router(domain: DomainService | None = None) -> APIRouter:
    router = APIRouter(tags=["Paper execution controls"])

    def executor(request: Request) -> PaperExecution:
        service = getattr(request.app.state, "paper_execution", None)
        if not isinstance(service, PaperExecution):
            raise HTTPException(409, "Paper execution is not activated")
        return service

    def status(service: PaperExecution) -> ExecutionControl:
        book = service.snapshot()
        return ExecutionControl(
            entries_locked=book.killed or book.loss_locked,
            pending_closures=sum(
                p.status != PositionStatus.CLOSED for p in book.positions.values()
            ),
        )

    @router.post("/api/kill")
    def kill(
        request: Request, idempotency_key: str | None = Header(default=None)
    ) -> ExecutionControl:
        # Mutation middleware enforces dashboard auth, origin, CSRF and audit.
        if domain is not None:
            return ExecutionControl.model_validate(
                domain.control(
                    "kill", None, idempotency_key or "legacy-kill"
                ).model_dump()
            )
        service = executor(request)
        service.kill(datetime.now(IST))
        return status(service)

    @router.post("/api/trades/{trade_id}/close")
    def close(
        trade_id: str,
        request: Request,
        idempotency_key: str | None = Header(default=None),
    ) -> ExecutionControl:
        if domain is not None:
            return ExecutionControl.model_validate(
                domain.control(
                    "close", trade_id, idempotency_key or "close:" + trade_id
                ).model_dump()
            )
        service = executor(request)
        try:
            service.close(trade_id, datetime.now(IST))
        except KeyError:
            raise HTTPException(404) from None
        return status(service)

    return router
