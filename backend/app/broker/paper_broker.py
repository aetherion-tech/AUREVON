"""Pure deterministic paper fills. Persist returned orders before further actions."""

from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from hashlib import sha256

from app.execution.models import (
    Fill,
    FillSettings,
    MarketPrice,
    Order,
    OrderStatus,
    Side,
)
from app.market.warmup import local_time


class PaperBroker:
    def __init__(self, settings: FillSettings) -> None:
        self.settings = settings

    def place(
        self,
        key: str,
        token: int,
        side: Side,
        quantity: int,
        tick: Decimal,
        at: datetime,
        limit: Decimal | None = None,
    ) -> Order:
        at = local_time(at)
        if (
            not key
            or token <= 0
            or type(quantity) is not int
            or quantity <= 0
            or not tick.is_finite()
            or tick <= 0
            or (
                limit is not None
                and (not limit.is_finite() or limit <= 0 or limit % tick)
            )
        ):
            raise ValueError("invalid order")
        return Order(
            id="P-" + sha256(key.encode()).hexdigest()[:32],
            key=key,
            token=token,
            side=side,
            quantity=quantity,
            tick=tick,
            at=at,
            eligible_at=at + timedelta(milliseconds=self.settings.latency_ms),
            limit=limit,
        )

    def valid(self, price: MarketPrice, at: datetime) -> bool:
        local_time(at)
        return all(
            0 <= (at - t).total_seconds() <= self.settings.quote_max_age_seconds
            for t in (price.at, price.received_at)
        )

    def process(self, order: Order, price: MarketPrice, at: datetime) -> Order:
        at = local_time(at)
        if (
            order.status != OrderStatus.PENDING
            or at < order.eligible_at
            or price.at < order.eligible_at
            or price.token != order.token
            or not self.valid(price, at)
        ):
            return order
        buy = order.side == Side.BUY
        if order.limit is not None:
            if (buy and price.last > order.limit) or (
                not buy and price.last < order.limit
            ):
                return order
            value = order.limit  # conservative: no invented price improvement
        elif price.bid is not None and price.ask is not None:
            available = price.ask_quantity if buy else price.bid_quantity
            if available < order.quantity:
                return order.model_copy(
                    update={
                        "status": OrderStatus.REJECTED,
                        "reason": "insufficient_depth",
                    }
                )
            value = price.ask if buy else price.bid
        else:
            value = price.last + self.settings.slippage * (1 if buy else -1)
        value = (value / order.tick).to_integral_value(
            rounding=ROUND_CEILING if buy else ROUND_FLOOR
        ) * order.tick
        if value <= 0 or abs(value - price.last) > price.last * Decimal(".05"):
            return order.model_copy(
                update={"status": OrderStatus.REJECTED, "reason": "price_sanity"}
            )
        costs = (
            self.settings.fee_per_order
            + value * order.quantity * self.settings.fee_bps / 10000
        ).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        parts: dict[str, Decimal] = {}
        schedule_id = None
        if self.settings.cost_schedule is not None:
            schedule = self.settings.cost_schedule
            try:
                parts = schedule.estimate(order.side, value * order.quantity, at.date())
            except ValueError:
                return order.model_copy(
                    update={
                        "status": OrderStatus.REJECTED,
                        "reason": "cost_schedule_unavailable",
                    }
                )
            costs = sum(parts.values(), Decimal(0))
            schedule_id = schedule.identity
        fill = Fill(
            id=order.id + "-F",
            at=at,
            price=value,
            quantity=order.quantity,
            costs=costs,
            cost_parts=parts,
            cost_schedule_id=schedule_id,
        )
        return order.model_copy(update={"status": OrderStatus.FILLED, "fill": fill})

    def cancel(self, order: Order) -> Order:
        if order.status != OrderStatus.PENDING:
            return order
        return order.model_copy(
            update={"status": OrderStatus.CANCELLED, "reason": "cancelled"}
        )
