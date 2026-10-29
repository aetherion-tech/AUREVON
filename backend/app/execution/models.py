"""Exact, persisted paper broker and lifecycle contracts."""

from datetime import date, time
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from app.api.schemas import ISTTimestamp
from app.strategy.models import Frozen, Nonnegative, Positive, TradePlan
from app.wallet.contracts import CostSchedule, WalletSettings, money


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class FillStatus(StrEnum):
    COMPLETE = "COMPLETE"


class PositionStatus(StrEnum):
    ENTERING = "ENTERING"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    UNWINDING = "UNWINDING"
    CLOSED = "CLOSED"


class Mode(Frozen):
    mode: str = "PAPER"
    armed: bool = False

    @model_validator(mode="after")
    def paper_only(self) -> "Mode":
        if self.mode != "PAPER" or self.armed:
            raise ValueError("live sending and arming unavailable")
        return self


class FillSettings(Frozen):
    version: Literal[1] = 1
    slippage: Nonnegative = Decimal("0.5")
    latency_ms: int = Field(default=500, ge=0, le=60000, strict=True)
    fee_per_order: Nonnegative = Decimal("0")
    fee_bps: Nonnegative = Decimal("0")
    # Assumptions only; never a claim about current broker/exchange charges.
    cost_basis: str = Field(default="USER_CONFIGURED_PAPER_ASSUMPTION", min_length=1)
    quote_max_age_seconds: int = Field(default=5, ge=1, le=60, strict=True)
    cost_schedule: CostSchedule | None = None

    @model_validator(mode="after")
    def one_cost_basis(self) -> "FillSettings":
        if self.cost_schedule is not None and (self.fee_per_order or self.fee_bps):
            raise ValueError("choose detailed schedule or legacy fees")
        return self


class RiskSettings(Frozen):
    version: Literal[1] = 1
    daily_loss_pct: Positive = Decimal("2")
    max_trade_loss_pct: Positive = Decimal("1")
    max_trades: int = Field(default=3, ge=1, strict=True)
    entry_start: time = time(9, 30)
    entry_end: time = time(14, 45)
    square_off: time = time(15, 15)
    max_plan_age_seconds: int = Field(default=5, ge=1, le=60, strict=True)

    @model_validator(mode="after")
    def times(self) -> "RiskSettings":
        if any(t.tzinfo for t in (self.entry_start, self.entry_end, self.square_off)):
            raise ValueError("local IST times required")
        if not self.entry_start < self.entry_end < self.square_off:
            raise ValueError("entry window must precede square-off")
        if self.daily_loss_pct > 100 or self.max_trade_loss_pct > 100:
            raise ValueError("risk percentage exceeds capital")
        return self


class Readiness(Frozen):
    at: ISTTimestamp
    feed: bool = False
    authenticated: bool = False
    recovered: bool = False
    indicators: bool = False
    clock: bool = False
    event_blocked: bool = True

    def ready(self) -> bool:
        return (
            all(
                (
                    self.feed,
                    self.authenticated,
                    self.recovered,
                    self.indicators,
                    self.clock,
                )
            )
            and not self.event_blocked
        )


class MarketPrice(Frozen):
    token: int = Field(gt=0, strict=True)
    at: ISTTimestamp
    received_at: ISTTimestamp
    last: Positive
    bid: Positive | None = None
    ask: Positive | None = None
    bid_quantity: int = Field(default=0, ge=0, strict=True)
    ask_quantity: int = Field(default=0, ge=0, strict=True)

    @model_validator(mode="after")
    def depth(self) -> "MarketPrice":
        if (self.bid is None) != (self.ask is None):
            raise ValueError("both sides required for depth")
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError("crossed market")
        if self.at > self.received_at:
            raise ValueError("future exchange timestamp")
        return self


class Fill(Frozen):
    status: Literal[FillStatus.COMPLETE] = FillStatus.COMPLETE
    id: str
    at: ISTTimestamp
    price: Positive
    quantity: int = Field(gt=0, strict=True)
    costs: Nonnegative
    cost_parts: dict[str, Nonnegative] = Field(default_factory=dict)
    cost_schedule_id: str | None = None

    @model_validator(mode="after")
    def costs_agree(self) -> "Fill":
        if self.cost_parts and sum(self.cost_parts.values()) != self.costs:
            raise ValueError("fill cost breakdown mismatch")
        return self


class Order(Frozen):
    id: str
    key: str
    token: int
    side: Side
    quantity: int
    tick: Positive
    at: ISTTimestamp
    eligible_at: ISTTimestamp
    limit: Positive | None = None
    status: OrderStatus = OrderStatus.PENDING
    fill: Fill | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def fill_consistent(self) -> "Order":
        if self.quantity <= 0 or self.token <= 0 or not self.id.startswith("P-"):
            raise ValueError("invalid paper order")
        if (self.status == OrderStatus.FILLED) != (self.fill is not None):
            raise ValueError("fill/status mismatch")
        if self.fill is not None and (
            self.fill.quantity != self.quantity
            or self.fill.at < self.eligible_at
            or self.fill.price % self.tick
        ):
            raise ValueError("invalid fill quantity/time/tick")
        return self


class Transition(Frozen):
    at: ISTTimestamp
    state: PositionStatus
    reason: str


class Position(Frozen):
    id: str
    decision_id: str
    plan: TradePlan
    status: PositionStatus = PositionStatus.ENTERING
    orders: dict[str, Order] = Field(default_factory=dict)
    transitions: tuple[Transition, ...] = ()
    exit_reason: str | None = None
    gross: Decimal = Decimal(0)
    costs: Nonnegative = Decimal(0)
    unrealised: Decimal | None = None
    mark_at: ISTTimestamp | None = None
    spread_debit: Decimal | None = None
    mark_prices: dict[int, MarketPrice] = Field(default_factory=dict)


class LedgerEntry(Frozen):
    key: str
    at: ISTTimestamp
    kind: str
    amount: Decimal
    balance: Decimal
    reserved: Nonnegative


class Rejection(Frozen):
    decision_id: str
    signal_id: str
    at: ISTTimestamp
    reasons: tuple[str, ...]


class PaperBook(Frozen):
    version: Literal[1] = 1
    mode: Mode = Field(default_factory=Mode)
    fill_settings: FillSettings
    risk_settings: RiskSettings
    balance: Decimal = Decimal(0)
    reserved: Nonnegative = Decimal(0)
    ledger: tuple[LedgerEntry, ...] = ()
    positions: dict[str, Position] = Field(default_factory=dict)
    rejects: dict[str, Rejection] = Field(default_factory=dict)
    day: date | None = None
    day_capital: Decimal = Decimal(0)
    day_net: Decimal = Decimal(0)
    day_trades: int = 0
    loss_locked: bool = False
    killed: bool = False
    last_at: ISTTimestamp | None = None
    wallet_settings: WalletSettings | None = None
    projected: bool = False

    @model_validator(mode="after")
    def reconcile(self) -> "PaperBook":
        balance, reserved = Decimal(0), Decimal(0)
        keys: set[str] = set()
        for e in self.ledger:
            if e.key in keys:
                raise ValueError("duplicate ledger key")
            keys.add(e.key)
            money(e.amount)
            money(e.balance)
            money(e.reserved)
            if e.kind in {
                "INITIAL",
                "DEPOSIT",
                "WITHDRAW",
                "RESET",
                "REALISED_GROSS",
                "COSTS",
            }:
                balance += e.amount
            elif e.kind in {"RESERVE", "RELEASE"}:
                reserved += e.amount
            else:
                raise ValueError("unknown ledger kind")
            if e.balance != balance or e.reserved != reserved or reserved < 0:
                raise ValueError("ledger balance/reservation mismatch")
        required = sum(
            (
                p.plan.required_margin
                for p in self.positions.values()
                if p.status != PositionStatus.CLOSED
            ),
            Decimal(0),
        )
        if balance != self.balance or reserved != self.reserved or required != reserved:
            raise ValueError("paper book reconciliation failed")
        if len({p.decision_id for p in self.positions.values()}) != len(self.positions):
            raise ValueError("duplicate decision")
        if len({p.plan.signal.signal_id for p in self.positions.values()}) != len(
            self.positions
        ):
            raise ValueError("duplicate signal")
        for identity, p in self.positions.items():
            if (
                identity != p.id
                or not p.transitions
                or p.transitions[-1].state != p.status
            ):
                raise ValueError("position transition mismatch")
            if p.status == PositionStatus.CLOSED and p.id + ":costs" not in keys:
                raise ValueError("closed position has no settlement")
            cash, costs = Decimal(0), Decimal(0)
            quantities = {
                p.plan.short.contract.token: 0,
                p.plan.hedge.contract.token: 0,
            }
            fill_ids: set[str] = set()
            for order in p.orders.values():
                if (
                    order.token not in quantities
                    or order.quantity != p.plan.short.quantity
                ):
                    raise ValueError("order differs from spread")
                if order.fill is None:
                    continue
                f = order.fill
                if f.id in fill_ids:
                    raise ValueError("duplicate fill")
                fill_ids.add(f.id)
                signed = f.quantity * (1 if order.side == Side.BUY else -1)
                quantities[order.token] += signed
                cash -= f.price * signed
                costs += f.costs
            short, hedge = (
                -quantities[p.plan.short.contract.token],
                quantities[p.plan.hedge.contract.token],
            )
            if not 0 <= short <= hedge <= p.plan.short.quantity:
                raise ValueError("unhedged paper exposure")
            if p.status == PositionStatus.CLOSED:
                if short or hedge or p.gross != cash or p.costs != costs:
                    raise ValueError("trade/fill settlement mismatch")
                entries = {e.key: e.amount for e in self.ledger}
                if (
                    entries.get(p.id + ":gross") != cash
                    or entries.get(p.id + ":costs") != -costs
                ):
                    raise ValueError("trade/ledger settlement mismatch")
        return self
