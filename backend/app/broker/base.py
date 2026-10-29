"""Shared order semantics. Real-order sending has no implementation."""

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.execution.models import MarketPrice, Order, Side


class Broker(Protocol):
    def place(
        self,
        key: str,
        token: int,
        side: Side,
        quantity: int,
        tick: Decimal,
        at: datetime,
        limit: Decimal | None = None,
    ) -> Order: ...

    def process(self, order: Order, price: MarketPrice, at: datetime) -> Order: ...

    def cancel(self, order: Order) -> Order: ...
