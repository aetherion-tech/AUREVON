"""One bounded ordered journal. Cursor overflow explicitly requires a snapshot."""

from collections import deque
from datetime import datetime
from threading import RLock
from time import monotonic
from typing import Literal
from uuid import uuid4

from app.api.live_contracts import (
    AlertData,
    BrickData,
    LiveEvent,
    LiveSnapshot,
    PositionData,
    SignalData,
    StatusData,
    TickData,
    TradeData,
)
from app.broker.kite_auth import IST


class EventHub:
    def __init__(self, capacity: int = 256) -> None:
        self.run_id = uuid4().hex
        self.sequence = 0
        self.lock = RLock()
        self.events: deque[LiveEvent] = deque(maxlen=capacity)
        if capacity < 1:
            raise ValueError("Event capacity must be positive")
        self.tick_at = -1e10
        self.latest: LiveSnapshot | None = None

    def publish(
        self,
        payload: TickData
        | BrickData
        | SignalData
        | TradeData
        | PositionData
        | StatusData
        | AlertData,
    ) -> LiveEvent | None:
        kinds: dict[
            type[object],
            Literal["tick", "brick", "signal", "trade", "position", "status", "alert"],
        ] = {
            TickData: "tick",
            BrickData: "brick",
            SignalData: "signal",
            TradeData: "trade",
            PositionData: "position",
            StatusData: "status",
            AlertData: "alert",
        }
        with self.lock:
            if isinstance(payload, TickData):
                now = monotonic()
                if now - self.tick_at < 0.25:
                    return None
                self.tick_at = now
            self.sequence += 1
            event = LiveEvent(
                run_id=self.run_id,
                sequence=self.sequence,
                at=datetime.now(IST),
                kind=kinds[type(payload)],
                payload=payload,
            )
            self.events.append(event.model_copy(deep=True))
            return event

    def since(self, run_id: str, sequence: int) -> list[LiveEvent] | None:
        with self.lock:
            if (
                run_id != self.run_id
                or sequence > self.sequence
                or sequence < 0
                or (self.events and sequence < self.events[0].sequence - 1)
            ):
                return None
            return [
                e.model_copy(deep=True) for e in self.events if e.sequence > sequence
            ]
