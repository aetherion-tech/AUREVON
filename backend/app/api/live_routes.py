"""Authenticated snapshots/history, durable alerts and bounded live transport."""

import asyncio
from contextlib import suppress
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.exc import SQLAlchemyError

from app.api.live_contracts import (
    AlertData,
    BrickHistory,
    CandleHistory,
    EventBatch,
    HeartbeatFrame,
    LiveSnapshot,
    ResyncFrame,
    SnapshotFrame,
)
from app.api.live_service import LiveService
from app.api.schemas import ISTTimestamp, Page
from app.api.security import DashboardSecurity


def live_router(service: LiveService, security: DashboardSecurity) -> APIRouter:
    router = APIRouter(tags=["Live dashboard"])
    protected = [Depends(security.require)]

    @router.get("/api/live/snapshot", dependencies=protected)
    async def snapshot() -> LiveSnapshot:
        return service.sample()

    @router.get("/api/market/service/status", dependencies=protected)
    async def status() -> LiveSnapshot:
        return service.sample()

    @router.post("/api/market/service/start")
    async def start(request: Request) -> LiveSnapshot:
        replay = request.app.state.replay_service
        if replay.task is not None and not replay.task.done():
            raise HTTPException(409)
        await service.market.start()
        return service.sample()

    @router.post("/api/market/service/stop")
    async def stop() -> LiveSnapshot:
        await service.market.stop()
        return service.sample()

    @router.get("/api/bricks", dependencies=protected)
    def bricks(
        stream: Annotated[str, Query(min_length=1, max_length=160)],
        after: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=300)] = 100,
        revision: Annotated[int | None, Query(ge=0)] = None,
    ) -> BrickHistory:
        return service.bricks(stream, after, limit, revision)

    @router.get("/api/candles", dependencies=protected)
    def candles(
        stream: Annotated[str, Query(min_length=1, max_length=160)],
        token: Annotated[int, Query(gt=0)],
        after: ISTTimestamp | None = None,
        limit: Annotated[int, Query(ge=1, le=300)] = 100,
        revision: Annotated[int | None, Query(ge=0)] = None,
    ) -> CandleHistory:
        return service.candles(stream, token, after, limit, revision)

    @router.get("/api/alerts", dependencies=protected)
    def alerts(
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    ) -> Page[AlertData]:
        return service.alerts(limit, offset)

    @router.post("/api/alerts/{identity}/ack")
    def acknowledge(identity: str) -> AlertData:
        return service.acknowledge(identity)

    @router.websocket("/ws/live")
    async def live(socket: WebSocket) -> None:
        if not security.websocket_allowed(socket):
            await socket.close(code=1008)
            return
        await socket.accept()
        reader: asyncio.Task[None] | None = None

        async def receive_disconnect() -> None:
            # Consume only to detect disconnect. No client mutation channel exists.
            while True:
                message = await socket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                if (
                    len(message.get("text", "")) > 4096
                    or len(message.get("bytes", b"")) > 4096
                ):
                    await socket.close(code=1009)
                    return

        try:
            initial = service.sample()
            run = socket.query_params.get("run_id")
            cursor_text = socket.query_params.get("after")
            if run is None and cursor_text is None:
                await asyncio.wait_for(
                    socket.send_json(
                        SnapshotFrame(snapshot=initial).model_dump(mode="json")
                    ),
                    2,
                )
                cursor = initial.sequence
                run = initial.run_id
            else:
                try:
                    cursor = int(cursor_text or "")
                except ValueError:
                    cursor = -1
                if run is None or service.hub.since(run, cursor) is None:
                    await socket.send_json(
                        ResyncFrame(
                            run_id=service.hub.run_id,
                            sequence=service.hub.sequence,
                            reason="run_changed"
                            if run != service.hub.run_id
                            else "cursor_expired",
                        ).model_dump(mode="json")
                    )
                    await socket.close(code=1013)
                    return
            reader = asyncio.create_task(receive_disconnect())
            heartbeat = asyncio.get_running_loop().time()
            while not reader.done():
                if not security.websocket_allowed(socket):
                    await socket.close(code=1008)
                    return
                service.sample()
                events = service.hub.since(run, cursor)
                if events is None:
                    await asyncio.wait_for(
                        socket.send_json(
                            ResyncFrame(
                                run_id=service.hub.run_id,
                                sequence=service.hub.sequence,
                                reason="cursor_expired",
                            ).model_dump(mode="json")
                        ),
                        2,
                    )
                    await socket.close(code=1013)
                    return
                if events:
                    await asyncio.wait_for(
                        socket.send_json(
                            EventBatch(
                                run_id=run, sequence=events[-1].sequence, events=events
                            ).model_dump(mode="json")
                        ),
                        2,
                    )
                    cursor = events[-1].sequence
                now = asyncio.get_running_loop().time()
                if now - heartbeat >= 5:
                    await asyncio.wait_for(
                        socket.send_json(
                            HeartbeatFrame(run_id=run, sequence=cursor).model_dump(
                                mode="json"
                            )
                        ),
                        2,
                    )
                    heartbeat = now
                await asyncio.sleep(0.25)
        except (WebSocketDisconnect, RuntimeError):
            pass
        except (TimeoutError, SQLAlchemyError):
            with suppress(RuntimeError, WebSocketDisconnect):
                await socket.close(code=1013)
        finally:
            if reader is not None:
                reader.cancel()
                with suppress(
                    asyncio.CancelledError, WebSocketDisconnect, RuntimeError
                ):
                    await reader

    return router
