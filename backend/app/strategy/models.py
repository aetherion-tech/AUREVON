"""Versioned, immutable strategy contracts with exact decimal JSON amounts."""

from datetime import date, time
from decimal import ROUND_CEILING, Decimal
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, StrictBool, field_validator, model_validator

from app.api.schemas import Contract, DecimalValue, ISTTimestamp

Positive = Annotated[DecimalValue, Field(gt=0, max_digits=24, decimal_places=6)]
Nonnegative = Annotated[DecimalValue, Field(ge=0, max_digits=24, decimal_places=6)]


class Frozen(Contract):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    @field_validator("version", mode="before", check_fields=False)
    @classmethod
    def strict_version(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("version must be an integer")
        return value


class StrategySettings(Frozen):
    version: Literal[1] = 1
    short_offset_steps: int = Field(default=1, ge=0, le=100, strict=True)
    hedge_width_steps: int = Field(default=4, ge=1, le=100, strict=True)
    hedge_mode: Literal["width", "premium"] = "width"
    hedge_target_premium: Positive = Decimal("7.50")
    premium_search_steps: int = Field(default=20, ge=1, le=100, strict=True)
    expiry_policy: Literal["skip", "trade_current", "trade_next"] = "trade_next"
    expiry_switch_at: time = time(12)
    liquidity_retries: int = Field(default=2, ge=0, le=2, strict=True)
    max_spread_pct: Nonnegative = Decimal("2")
    max_spread_abs: Nonnegative = Decimal("1")
    min_open_interest: int = Field(default=1, ge=0, strict=True)
    quote_max_age_seconds: int = Field(default=5, ge=1, le=60, strict=True)
    quote_max_skew_seconds: int = Field(default=2, ge=0, le=10, strict=True)
    minimum_credit: Positive = Decimal("0.05")
    sizing: Literal["fixed_lots", "risk_pct"] = "fixed_lots"
    fixed_lots: int = Field(default=1, ge=1, le=10000, strict=True)
    risk_pct: Annotated[DecimalValue, Field(gt=0, le=100)] = Decimal("1")
    max_lots: int = Field(default=10, ge=1, le=10000, strict=True)
    max_quantity: int = Field(default=10000, ge=1, strict=True)
    margin_buffer_pct: Annotated[Nonnegative, Field(le=1000)] = Decimal("10")
    sl_pct_of_max_loss: Annotated[DecimalValue, Field(gt=0, le=100)] = Decimal("50")
    profit_capture_enabled: StrictBool = False
    profit_capture_pct: Annotated[DecimalValue, Field(gt=0, le=100)] = Decimal("70")
    entry_start: time = time(9, 30)
    entry_end: time = time(14, 45)
    min_grade: int = Field(default=2, ge=1, le=3, strict=True)
    allowed_families: tuple[Literal["CO", "DIV", "OT"], ...] = ("CO", "DIV", "OT")
    skip_high_risk: StrictBool = True
    skip_opposite_bias: StrictBool = True

    @model_validator(mode="after")
    def valid_times(self) -> "StrategySettings":
        if (
            any(
                t.tzinfo is not None
                for t in (self.entry_start, self.entry_end, self.expiry_switch_at)
            )
            or self.entry_start >= self.entry_end
        ):
            raise ValueError("use ordered local IST entry times")
        if not self.allowed_families or len(set(self.allowed_families)) != len(
            self.allowed_families
        ):
            raise ValueError("unique nonempty allowed families required")
        return self


class SignalInput(Frozen):
    version: Literal[1] = 1
    signal_id: str = Field(min_length=1, max_length=160)
    trade_id: str = Field(pattern=r"^\[.{5}\]$")
    direction: Literal[1, -1]
    family: Literal["CO", "DIV", "OT"]
    grade: int = Field(ge=1, le=3, strict=True)
    risk: Literal["Low", "Medium", "High"]
    bias_direction: Literal[-1, 0, 1]
    at: ISTTimestamp
    spot: Positive
    index_target_1: Positive
    index_target_2: Positive
    replaced_trade_id: str | None = None

    @model_validator(mode="after")
    def target_direction(self) -> "SignalInput":
        if any(
            self.direction * (target - self.spot) <= 0
            for target in (self.index_target_1, self.index_target_2)
        ):
            raise ValueError("index targets must agree with signal direction")
        return self

    @field_validator("direction", "bias_direction", mode="before")
    @classmethod
    def strict_direction(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("direction must be an integer")
        return value

    @classmethod
    def from_indicator(
        cls, stream: str, result: dict[str, Any], ordinal: int
    ) -> "SignalInput":
        event = result["events"][ordinal]
        if result.get("schema_version") != 1 or event["kind"] != "ENTRY":
            raise ValueError("version-1 indicator ENTRY required")
        accepted = next(
            s
            for s in result["signals"]
            if s["accepted"]
            and s["type"] == event["type"]
            and s["direction"] == event["direction"]
        )
        from datetime import datetime

        from app.market.renko_builder import IST

        return cls(
            signal_id=f"{stream}:{result['index']}:{ordinal}",
            trade_id=event["trade_id"],
            direction=event["direction"],
            family="CO"
            if event["type"] == "CORE"
            else "DIV"
            if event["type"] in ("DIV", "HDIV")
            else "OT",
            grade=event["grade"],
            risk=accepted["risk"]["label"],
            bias_direction=result["bias_direction"],
            at=datetime.fromtimestamp(result["time_ms"] / 1000, IST),
            spot=Decimal(str(event["price"])),
            index_target_1=Decimal(str(event["target_1"])),
            index_target_2=Decimal(str(event["target_2"])),
            replaced_trade_id=event.get("replaced_trade_id"),
        )


class OptionContract(Frozen):
    token: int = Field(gt=0, strict=True)
    exchange: Literal["NFO"] = "NFO"
    name: Literal["NIFTY"] = "NIFTY"
    symbol: str = Field(min_length=1, max_length=100)
    expiry: date
    strike: Positive
    option_type: Literal["CE", "PE"]
    lot_size: int = Field(gt=0, strict=True)
    tick_size: Positive


class Catalog(Frozen):
    loaded_at: ISTTimestamp
    contracts: tuple[OptionContract, ...]

    @model_validator(mode="after")
    def identities(self) -> "Catalog":
        if (
            len({c.token for c in self.contracts}) != len(self.contracts)
            or len({c.symbol for c in self.contracts}) != len(self.contracts)
            or len({(c.expiry, c.option_type, c.strike) for c in self.contracts})
            != len(self.contracts)
        ):
            raise ValueError("ambiguous option catalog")
        return self


class DepthLevel(Frozen):
    price: Positive
    quantity: int = Field(gt=0, strict=True)


class OptionQuote(Frozen):
    contract: OptionContract
    exchange_at: ISTTimestamp
    received_at: ISTTimestamp
    bids: tuple[DepthLevel, ...] = Field(min_length=1, max_length=5)
    asks: tuple[DepthLevel, ...] = Field(min_length=1, max_length=5)
    open_interest: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def ordered(self) -> "OptionQuote":
        if any(a.price < b.price for a, b in zip(self.bids, self.bids[1:])) or any(
            a.price > b.price for a, b in zip(self.asks, self.asks[1:])
        ):
            raise ValueError("unordered option depth")
        if self.bids[0].price > self.asks[0].price:
            raise ValueError("crossed option market")
        return self


class CapitalSnapshot(Frozen):
    at: ISTTimestamp
    free_capital: Nonnegative
    source: Literal["PAPER_WALLET", "USER_PREVIEW"]
    revision: str = Field(min_length=1, max_length=160)


class PlanLeg(Frozen):
    role: Literal["SHORT", "HEDGE"]
    side: Literal["SELL", "BUY"]
    contract: OptionContract
    quantity: int = Field(gt=0, strict=True)
    limit_price: Positive


class TradePlan(Frozen):
    version: Literal[1] = 1
    plan_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    signal: SignalInput
    planned_at: ISTTimestamp
    structure: Literal["BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"]
    expiry: date
    strike_step: Positive
    lots: int = Field(gt=0, strict=True)
    short: PlanLeg
    hedge: PlanLeg
    credit_per_unit: Positive
    credit: Positive
    maximum_loss: Positive
    stop_debit_per_unit: Annotated[DecimalValue, Field(gt=0)]
    profit_capture_debit_per_unit: Annotated[DecimalValue, Field(ge=0)]
    profit_capture_enabled: bool
    required_margin: Positive
    margin_source: Literal["PAPER_ESTIMATE"] = "PAPER_ESTIMATE"
    broker_reported_margin: None = None
    payoff_basis: Literal["GROSS_BEFORE_FEES"] = "GROSS_BEFORE_FEES"
    capital: CapitalSnapshot
    settings: StrategySettings
    catalog_loaded_at: ISTTimestamp
    short_quote_at: ISTTimestamp
    hedge_quote_at: ISTTimestamp
    executable: Literal[False] = False

    @model_validator(mode="after")
    def spread_invariants(self) -> "TradePlan":
        short, hedge = self.short, self.hedge
        contracts = (short.contract, hedge.contract)
        sd = self.signal.direction
        width = sd * (short.contract.strike - hedge.contract.strike)
        quantity = self.lots * short.contract.lot_size
        per_lot = (width - self.credit_per_unit) * short.contract.lot_size
        expected_margin = (
            per_lot * (1 + self.settings.margin_buffer_pct / 100)
        ).quantize(Decimal(".01"), rounding=ROUND_CEILING) * self.lots
        if (
            short.role != "SHORT"
            or short.side != "SELL"
            or hedge.role != "HEDGE"
            or hedge.side != "BUY"
            or short.contract.token == hedge.contract.token
            or width <= 0
            or any(
                c.expiry != self.expiry or c.option_type != ("PE" if sd == 1 else "CE")
                for c in contracts
            )
            or self.structure != ("BULL_PUT_SPREAD" if sd == 1 else "BEAR_CALL_SPREAD")
            or short.contract.lot_size != hedge.contract.lot_size
            or short.quantity != quantity
            or hedge.quantity != quantity
            or short.limit_price % short.contract.tick_size
            or hedge.limit_price % hedge.contract.tick_size
            or self.credit_per_unit != short.limit_price - hedge.limit_price
            or self.credit != self.credit_per_unit * quantity
            or self.maximum_loss != (width - self.credit_per_unit) * quantity
            or self.required_margin < self.maximum_loss
            or self.required_margin != expected_margin
            or self.required_margin > self.capital.free_capital
            or self.lots > self.settings.max_lots
            or quantity > self.settings.max_quantity
            or self.stop_debit_per_unit
            != self.credit_per_unit
            + (width - self.credit_per_unit) * self.settings.sl_pct_of_max_loss / 100
            or self.profit_capture_debit_per_unit
            != self.credit_per_unit * (1 - self.settings.profit_capture_pct / 100)
            or self.profit_capture_enabled != self.settings.profit_capture_enabled
        ):
            raise ValueError("inconsistent two-leg credit-spread plan")
        return self


class PlanAttempt(Frozen):
    short_symbol: str | None = None
    hedge_symbol: str | None = None
    reason: str


class PlanDecision(Frozen):
    version: Literal[1] = 1
    decision_id: str | None = None
    accepted: bool
    reason: str
    plan: TradePlan | None = None
    candidates: tuple[OptionContract, ...] = ()
    attempts: tuple[PlanAttempt, ...] = ()
    executable: Literal[False] = False

    @model_validator(mode="after")
    def consistent(self) -> "PlanDecision":
        if self.accepted != (self.plan is not None):
            raise ValueError("accepted decision must carry exactly one plan")
        return self
