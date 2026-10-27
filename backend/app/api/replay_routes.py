"""Opt-in development replay into a new SQLite database, never the market stream."""

import asyncio
import tempfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.api.schemas import Contract
from app.api.security import DashboardSecurity
from app.config import Settings
from app.db.models import Base
from app.db.session import database_engine
from app.market.exchange_calendar import ExchangeCalendar
from app.market.persistence import MarketPersistence
from app.market.production_replay import replay_to_persistence
from app.market.service import MarketService, blocking
from app.market.warmup import SessionCalendar


class ReplayRequest(Contract):
    source_run: str = Field(pattern=r"^[0-9a-f]{32}$")
    files: list[str] = Field(min_length=1, max_length=30)
    spot_token: int = Field(gt=0)
    future_token: int = Field(gt=0)
    box: str = Field(pattern=r"^[0-9]{1,8}(\.[0-9]{1,6})?$")
    anchor: str = Field(pattern=r"^[0-9]{1,8}(\.[0-9]{1,6})?$")


class ReplayStatus(Contract):
    id: str
    state: Literal["running", "completed", "failed"]
    mode: Literal["PAPER"] = "PAPER"
    entries_enabled: Literal[False] = False
    failure: Literal["invalid_recording_or_replay_failed"] | None = None
    events: int | None = None
    bricks: int | None = None


class ReplayService:
    def __init__(self, settings: Settings, market: MarketService) -> None:
        self.settings, self.market = settings, market
        self.task: asyncio.Task[None] | None = None
        self.status: ReplayStatus | None = None
        self.closed = False

    def allowed(self) -> None:
        if not self.settings.development_replay_enabled:
            raise HTTPException(404)
        if self.closed or self.market.desired or self.market.worker is not None:
            raise HTTPException(409)

    async def start(self, request: ReplayRequest) -> ReplayStatus:
        self.allowed()
        if self.task is not None and not self.task.done():
            raise HTTPException(409)
        # Validation before scheduling; paths are resolved again in the job.
        self._paths(request)
        identity = uuid4().hex
        self.status = ReplayStatus(id=identity, state="running")
        self.task = asyncio.create_task(self._run(identity, request))
        return self.status

    def _paths(self, request: ReplayRequest) -> list[Path]:
        from datetime import date

        root = self.settings.market_record_dir.resolve()
        run = (root / request.source_run).resolve()
        if not run.is_relative_to(root) or not run.is_dir():
            raise HTTPException(422)
        paths = []
        if len(set(request.files)) != len(request.files) or request.files != sorted(
            request.files
        ):
            raise HTTPException(422)
        for name in request.files:
            try:
                if len(name) != 16 or name[10:] != ".jsonl":
                    raise ValueError
                date.fromisoformat(name[:10])
            except ValueError:
                raise HTTPException(422) from None
            path = (run / name).resolve()
            if path.parent != run or not path.is_file():
                raise HTTPException(422)
            paths.append(path)
        if (
            sum(path.stat().st_size for path in paths)
            > self.settings.development_replay_max_bytes
        ):
            raise HTTPException(413)
        if request.spot_token == request.future_token:
            raise HTTPException(422)
        return paths

    def _execute(self, request: ReplayRequest) -> tuple[int, int]:
        # Copy bounded inputs first: provenance hashes describe exactly the bytes
        # validated and replayed, even if the original recording is still growing.
        with tempfile.TemporaryDirectory(prefix="aurevon-replay-") as directory:
            root = Path(directory)
            copied = []
            remaining = self.settings.development_replay_max_bytes
            for path in self._paths(request):
                target = root / path.name
                with path.open("rb") as source, target.open("wb") as destination:
                    while chunk := source.read(min(65536, remaining + 1)):
                        remaining -= len(chunk)
                        if remaining < 0:
                            raise ValueError("Replay exceeds input limit")
                        destination.write(chunk)
                copied.append(target)
            engine = database_engine(f"sqlite:///{(root / 'replay.db').as_posix()}")
            try:
                Base.metadata.create_all(engine)
                store = MarketPersistence(
                    engine,
                    "replay-" + uuid4().hex,
                    request.spot_token,
                    request.future_token,
                    box=request.box,
                    anchor=request.anchor,
                )
                from datetime import date

                dates = [date.fromisoformat(p.name[:10]) for p in copied]
                calendars = ExchangeCalendar(self.settings.market_calendar_dir)
                years = [
                    calendars.year(y) for y in range(dates[0].year, dates[-1].year + 1)
                ]
                calendar = SessionCalendar(
                    dates[0],
                    dates[-1],
                    tuple(
                        s
                        for year in years
                        for s in year.sessions
                        if dates[0] <= s.opening.date() <= dates[-1]
                    ),
                )
                result = replay_to_persistence(copied, store, calendar)
                return int(result["events"]), int(result["bricks"])
            finally:
                engine.dispose()

    async def _run(self, identity: str, request: ReplayRequest) -> None:
        try:
            events, bricks = await blocking(lambda: self._execute(request))
            self.status = ReplayStatus(
                id=identity, state="completed", events=events, bricks=bricks
            )
        except Exception:
            self.status = ReplayStatus(
                id=identity,
                state="failed",
                failure="invalid_recording_or_replay_failed",
            )

    async def close(self) -> None:
        self.closed = True
        if self.task is not None:
            await self.task


def replay_router(service: ReplayService, security: DashboardSecurity) -> APIRouter:
    router = APIRouter(tags=["Development replay"])

    @router.post("/api/dev/replay", status_code=202)
    async def replay(body: ReplayRequest) -> ReplayStatus:
        return await service.start(body)

    @router.get("/api/dev/replay/{identity}", dependencies=[Depends(security.require)])
    def status(identity: str) -> ReplayStatus:
        if not service.settings.development_replay_enabled or service.status is None:
            raise HTTPException(404)
        if identity != service.status.id:
            raise HTTPException(404)
        return service.status

    return router
