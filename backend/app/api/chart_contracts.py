"""Public chart overlays. Indicator plans and markers never represent broker fills."""

from typing import Literal

from pydantic import Field, FiniteFloat, JsonValue

from app.api.schemas import Contract, ISTTimestamp


class ChartEvent(Contract):
    kind: Literal["ENTRY", "T1", "EXIT"]
    trade_id: str
    direction: Literal[-1, 1]
    price: FiniteFloat
    tooltip: str
    target_1: FiniteFloat | None = None
    target_2: FiniteFloat | None = None
    stop: FiniteFloat | None = None
    reason: str | None = None
    replaced_trade_id: str | None = None


class ChartPosition(Contract):
    posDir: Literal[-1, 0, 1]
    posEntry: FiniteFloat | None
    posStop: FiniteFloat | None
    posT1: FiniteFloat | None
    posT2: FiniteFloat | None
    posBar: int | None
    posT1Hit: bool
    posType: str
    posGrade: int
    posId: str


class IndicatorOverlay(Contract):
    index: int = Field(ge=0)
    at: ISTTimestamp
    supertrend: FiniteFloat | None
    supertrend_direction: Literal[-1, 1]
    rsi: FiniteFloat | None
    atr: FiniteFloat | None
    bias_direction: Literal[-1, 0, 1]
    bias_score: int
    bias_strong: bool
    factors: dict[str, int]
    support: FiniteFloat | None
    resistance: FiniteFloat | None
    up_trigger: FiniteFloat
    down_trigger: FiniteFloat
    up_probability: FiniteFloat | None = Field(ge=0, le=100)
    position: ChartPosition
    events: list[ChartEvent]


class IndicatorHistorySource(Contract):
    source_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    market_revision: int = Field(ge=0)
    configuration_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings: dict[str, JsonValue]
    last_index: int = Field(ge=0)
    mode: Literal["INDICATOR_REPLAY"] = "INDICATOR_REPLAY"
    reference_verified: Literal[False] = False
