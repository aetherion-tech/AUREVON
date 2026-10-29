"""Versioned user-configured paper assumptions; all INR stored as exact paise."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from app.api.schemas import DecimalValue
from app.strategy.models import Frozen, Nonnegative

MAX_MONEY = Decimal("999999999999.99")
PAISE = Decimal(".01")
Money = Annotated[DecimalValue, Field(max_digits=14, decimal_places=2)]
Rate = Annotated[Nonnegative, Field(le=100)]


def money(value: Decimal) -> Decimal:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or abs(value) > MAX_MONEY
    ):
        raise ValueError("amount exceeds exact wallet precision")
    if value != value.quantize(PAISE):
        raise ValueError("exact paise required")
    return value


def rounded(value: Decimal) -> Decimal:
    return money(value.quantize(PAISE, rounding=ROUND_HALF_UP))


class WalletSettings(Frozen):
    version: Literal[1] = 1
    initial_capital: Annotated[Money, Field(ge=0)] = Decimal("1000000.00")
    auto_topup: StrictBool = False


class CostSchedule(Frozen):
    version: Literal[1] = 1
    identity: str = Field(min_length=1, max_length=160)
    effective_from: date
    effective_to: date
    source: str = Field(min_length=1, max_length=500)
    basis: Literal["PAPER_ESTIMATE"] = "PAPER_ESTIMATE"
    brokerage_per_order: Annotated[Money, Field(ge=0)] = Decimal(0)
    exchange_pct: Rate = Decimal(0)
    sebi_pct: Rate = Decimal(0)
    ipft_pct: Rate = Decimal(0)
    stt_sell_pct: Rate = Decimal(0)
    stamp_buy_pct: Rate = Decimal(0)
    gst_pct: Rate = Decimal(0)
    gst_on_ipft: StrictBool = False

    @model_validator(mode="after")
    def dates(self) -> "CostSchedule":
        if self.effective_to < self.effective_from:
            raise ValueError("ordered effective dates required")
        return self

    def estimate(self, side: str, turnover: Decimal, day: date) -> dict[str, Decimal]:
        if side not in {"BUY", "SELL"} or not turnover.is_finite() or turnover <= 0:
            raise ValueError("valid side and turnover required")
        if not self.effective_from <= day <= self.effective_to:
            raise ValueError("cost schedule outside effective dates")
        parts = {
            "brokerage": self.brokerage_per_order,
            "exchange": rounded(turnover * self.exchange_pct / 100),
            "sebi": rounded(turnover * self.sebi_pct / 100),
            "ipft": rounded(turnover * self.ipft_pct / 100),
            "stt": rounded(turnover * self.stt_sell_pct / 100)
            if side == "SELL"
            else Decimal(0),
            "stamp": rounded(turnover * self.stamp_buy_pct / 100)
            if side == "BUY"
            else Decimal(0),
        }
        taxable = parts["brokerage"] + parts["exchange"] + parts["sebi"]
        if self.gst_on_ipft:
            taxable += parts["ipft"]
        parts["gst"] = rounded(taxable * self.gst_pct / 100)
        return parts
