"""Versioned public PAPER domain contracts. No credentials or activation switches."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, JsonValue, StrictBool, field_validator, model_validator

from app.api.schemas import Contract, DecimalValue, ISTTimestamp, RupeeAmount
from app.execution.models import (
    FillSettings,
    OrderStatus,
    PositionStatus,
    RiskSettings,
    Side,
)
from app.indicator.settings import IndicatorSettings
from app.strategy.models import Frozen, StrategySettings
from app.wallet.contracts import WalletSettings


class SignalRecord(Contract):
    id: str
    stream: str
    index: int
    ordinal: int
    at: ISTTimestamp
    code: str
    direction: Literal[-1, 1]
    grade: int
    risk: str
    accepted: bool
    reason: str
    explanation: str
    entry_event_ordinal: int | None = None
    signal_id: str | None = None
    mode: Literal["INDICATOR_REPLAY"] = "INDICATOR_REPLAY"


class DecisionView(Contract):
    id: str
    signal_id: str
    at: ISTTimestamp
    kind: Literal["PREVIEW", "RISK_REJECT", "PAPER_ADMISSION"]
    accepted: bool
    reasons: list[str]
    explanation: str
    trade_id: str | None = None
    executable: Literal[False] = False


class WalletView(Contract):
    mode: Literal["PAPER"] = "PAPER"
    initialized: bool
    balance: RupeeAmount
    free: RupeeAmount
    reserved: RupeeAmount
    auto_topup: bool
    killed: bool
    loss_locked: bool
    day_trades: int


class LedgerView(Contract):
    sequence: int
    key: str
    at: ISTTimestamp
    kind: str
    amount: RupeeAmount
    balance: RupeeAmount
    reserved: RupeeAmount


class MoneyAction(Frozen):
    amount: Annotated[RupeeAmount, Field(gt=0, le=Decimal("999999999999.99"))]


class ResetAction(Frozen):
    amount: Annotated[RupeeAmount, Field(ge=0, le=Decimal("999999999999.99"))]
    confirm: Literal["RESET PAPER WALLET"]


class ActionResult(Contract):
    mode: Literal["PAPER"] = "PAPER"
    accepted: bool
    trade_id: str | None = None
    reason: str
    state: PositionStatus | None = None


class PrepareDecision(Frozen):
    stream: str = Field(min_length=1, max_length=160)
    index: int = Field(ge=0, strict=True)
    event_ordinal: int = Field(ge=0, strict=True)


class LegView(Contract):
    role: Literal["SHORT", "HEDGE"]
    symbol: str
    token: int
    quantity: int
    entry: DecimalValue | None
    mark: DecimalValue | None


class PositionView(Contract):
    trade_id: str
    decision_id: str
    mode: Literal["PAPER"] = "PAPER"
    state: PositionStatus
    created_at: ISTTimestamp
    mark_at: ISTTimestamp | None
    legs: list[LegView]
    margin: RupeeAmount
    gross: RupeeAmount
    costs: RupeeAmount
    net: RupeeAmount
    unrealised: RupeeAmount | None
    spread_debit: DecimalValue | None
    exit_reason: str | None
    orders: list["OrderView"]


class OrderView(Contract):
    id: str
    status: OrderStatus
    side: Side
    token: int
    quantity: int
    filled_at: ISTTimestamp | None
    fill_price: DecimalValue | None
    costs: RupeeAmount | None
    reason: str | None


class ExecutionControl(Contract):
    mode: Literal["PAPER"] = "PAPER"
    armed: Literal[False] = False
    entries_locked: bool
    pending_closures: int


class TradeRecord(Contract):
    trade_id: str
    closed_at: ISTTimestamp
    day: date
    family: Literal["CO", "DIV", "OT"]
    direction: Literal[-1, 1]
    grade: int
    result: Literal["WIN", "LOSS", "FLAT"]
    gross: RupeeAmount
    costs: RupeeAmount
    net: RupeeAmount
    margin: RupeeAmount
    entry_capital: RupeeAmount
    margin_return_pct: DecimalValue | None
    capital_return_pct: DecimalValue | None
    reason: str | None
    short_symbol: str
    hedge_symbol: str


class TradePage(Contract):
    items: list[TradeRecord]
    next_cursor: str | None
    revision: int
    mode: Literal["PAPER"] = "PAPER"


class PnlSummary(Contract):
    start: date
    end: date
    starting_capital: RupeeAmount
    trades: int
    wins: int
    gross: RupeeAmount
    costs: RupeeAmount
    net: RupeeAmount
    external_flows: RupeeAmount
    capital_return_pct: DecimalValue | None
    by_family_net: dict[str, RupeeAmount]
    basis: Literal["CLOSED_TRADES_NET_OF_ESTIMATED_COSTS"]


class DataSettings(Frozen):
    mode: Literal["minute_close", "tick"] = "minute_close"
    box: Annotated[DecimalValue, Field(gt=0)] = Decimal(50)
    anchor: DecimalValue | None = None
    lookback_days: int = Field(default=20, ge=1, le=250, strict=True)


class DisplaySettings(Frozen):
    theme: Literal["dark", "light"] = "dark"
    sounds: StrictBool = False


class SettingsBundle(Frozen):
    version: Literal[1] = 1
    pine: dict[str, JsonValue] = Field(
        default_factory=lambda: IndicatorSettings().values
    )
    strategy: StrategySettings = Field(default_factory=StrategySettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    fills: FillSettings = Field(default_factory=FillSettings)
    wallet: WalletSettings = Field(default_factory=WalletSettings)
    data: DataSettings = Field(default_factory=DataSettings)
    display: DisplaySettings = Field(default_factory=DisplaySettings)

    @field_validator("pine")
    @classmethod
    def canonical_inputs(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return IndicatorSettings(**value).values

    @model_validator(mode="after")
    def grid(self) -> "SettingsBundle":
        if Decimal(str(self.pine["boxSize"])) != self.data.box:
            raise ValueError("Pine boxSize must match the data grid")
        return self


class SettingsView(Contract):
    revision: int
    settings: SettingsBundle
    requires_rebuild: bool
    activation: Literal["owner_rebind_required", "defaults", "active"]


class SettingsUpdate(Frozen):
    expected_revision: int = Field(ge=0, strict=True)
    settings: SettingsBundle
    rebuild: StrictBool = False


class SettingsSchema(Contract):
    version: Literal[1] = 1
    pine_inputs: dict[str, JsonValue]
