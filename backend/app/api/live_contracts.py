"""Typed dashboard data and transport contracts; absent producers stay unavailable."""

from typing import Literal

from pydantic import Field, JsonValue, model_validator

from app.api.chart_contracts import IndicatorHistorySource, IndicatorOverlay
from app.api.domain_contracts import PnlSummary, PositionView, SignalRecord, WalletView
from app.api.schemas import Contract, DecimalValue, ISTTimestamp, RupeeAmount


class SelectedInstrument(Contract):
    spot: int
    future: int
    symbol: str
    expiry: str
    lot_size: int
    tick_size: DecimalValue


class DataQuality(Contract):
    connected: bool = False
    stale: bool = True
    clock_or_feed_delay: bool = True
    gap_requires_replay: bool = True
    reconnect_exhausted: bool = False
    history_pending: bool = True
    readiness: dict[str, JsonValue] = Field(default_factory=dict)


class TickData(Contract):
    token: int = Field(gt=0)
    price: DecimalValue
    time: ISTTimestamp


class BrickData(Contract):
    index: int
    open: DecimalValue
    close: DecimalValue
    direction: Literal[-1, 1]
    ts: ISTTimestamp
    volume: DecimalValue
    wick_high: DecimalValue | None = None
    wick_low: DecimalValue | None = None

    @model_validator(mode="after")
    def valid_wicks(self) -> "BrickData":
        if (self.wick_high is None) != (self.wick_low is None):
            raise ValueError("Both Renko wick extrema are required")
        if (
            self.wick_high is not None
            and self.wick_low is not None
            and not (
                0
                < self.wick_low
                <= min(self.open, self.close)
                <= max(self.open, self.close)
                <= self.wick_high
            )
        ):
            raise ValueError("Invalid Renko wick OHLC")
        return self


class LiveSnapshot(Contract):
    run_id: str
    sequence: int
    at: ISTTimestamp
    mode: Literal["PAPER"] = "PAPER"
    armed: Literal[False] = False
    entries_enabled: bool = False
    state: str
    desired: bool
    selected: SelectedInstrument | None
    quality: DataQuality
    recovery: dict[str, JsonValue]
    context: dict[str, JsonValue]
    ticks: list[TickData]
    latest_brick: BrickData | None
    stream: str
    configuration_id: str
    wallet: WalletView | None = None
    pnl: PnlSummary | None = None
    positions: list[PositionView] = Field(default_factory=list)
    signals: list["SignalData"] = Field(default_factory=list)
    last_trade: PositionView | None = None
    unavailable: list[str] = Field(
        default_factory=lambda: [
            "indicators",
            "signals",
            "execution",
            "positions",
            "wallet",
            "pnl",
        ]
    )


class StatusData(Contract):
    state: str
    desired: bool
    selected: SelectedInstrument | None
    quality: DataQuality
    recovery: dict[str, JsonValue]
    context: dict[str, JsonValue]
    entries_enabled: bool = False
    wallet: WalletView | None = None
    pnl: PnlSummary | None = None


class SignalData(Contract):
    id: str
    code: str
    accepted: bool
    reason: str
    explanation: str
    mode: Literal["INDICATOR_REPLAY"] = "INDICATOR_REPLAY"
    detail: SignalRecord | None = None


class TradeData(Contract):
    trade_id: str
    event: str
    mode: Literal["PAPER"] = "PAPER"


class PositionData(Contract):
    trade_id: str
    state: str
    mtm: RupeeAmount | None
    detail: PositionView | None = None


class AlertData(Contract):
    id: str
    level: Literal["info", "warning", "critical"]
    code: str
    at: ISTTimestamp
    acknowledged_at: ISTTimestamp | None = None


class LiveEvent(Contract):
    api_version: Literal["1.0"] = "1.0"
    run_id: str
    sequence: int = Field(ge=1)
    at: ISTTimestamp
    kind: Literal["tick", "brick", "signal", "trade", "position", "status", "alert"]
    payload: (
        TickData
        | BrickData
        | SignalData
        | TradeData
        | PositionData
        | StatusData
        | AlertData
    )

    @model_validator(mode="after")
    def matching_payload(self) -> "LiveEvent":
        expected = {
            "tick": TickData,
            "brick": BrickData,
            "signal": SignalData,
            "trade": TradeData,
            "position": PositionData,
            "status": StatusData,
            "alert": AlertData,
        }
        if not isinstance(self.payload, expected[self.kind]):
            raise ValueError("Event kind and payload must agree")
        return self


class EventBatch(Contract):
    type: Literal["events"] = "events"
    run_id: str
    sequence: int
    events: list[LiveEvent]


class SnapshotFrame(Contract):
    type: Literal["snapshot"] = "snapshot"
    snapshot: LiveSnapshot


class ResyncFrame(Contract):
    type: Literal["resync_required"] = "resync_required"
    run_id: str
    sequence: int
    reason: Literal["cursor_expired", "run_changed", "slow_consumer"]


class HeartbeatFrame(Contract):
    type: Literal["heartbeat"] = "heartbeat"
    run_id: str
    sequence: int


class CandleData(Contract):
    time: ISTTimestamp
    end: ISTTimestamp
    open: DecimalValue
    high: DecimalValue
    low: DecimalValue
    close: DecimalValue
    volume: DecimalValue | None
    oi: DecimalValue | None
    vwap: DecimalValue | None
    partial: bool
    vwap_partial: bool


class HistoryIdentity(Contract):
    stream: str
    revision: int
    configuration_id: str
    configuration: dict[str, JsonValue]


class BrickHistory(HistoryIdentity):
    indicators_available: bool = False
    items: list[BrickData]
    next_after: int | None
    indicator_source: IndicatorHistorySource | None = None
    overlays: list[IndicatorOverlay] = Field(default_factory=list)
    missing_overlay_indices: list[int] = Field(default_factory=list)
    overlay_status: Literal["unavailable", "partial", "complete", "empty"] = (
        "unavailable"
    )
    overlay_reason: Literal[
        "not_published", "source_changed", "indicator_advanced", "none"
    ] = "not_published"


class CandleHistory(HistoryIdentity):
    indicators_available: Literal[False] = False
    token: int
    items: list[CandleData]
    next_after: str | None
