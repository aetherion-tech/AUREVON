"""Replay-only complete Pine indicator; callers retain market readiness ownership."""

import copy
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from app.indicator.engine import IndicatorEngine
from app.indicator.features import divergence, outlook_bias
from app.indicator.settings import IndicatorSettings
from app.indicator.signals import accept_signal, raw_signals, select_signals
from app.indicator.trades import explanation, signal_statistics, trade_step
from app.market.renko_builder import IST, Brick


@dataclass(frozen=True)
class PineContext:
    """Point-in-time source context. None remains Pine na, never a guessed price.

    Pass only completed/available source context as of the brick. ORB uses Renko
    OHLC at 09:15–09:30 exactly as Pine, distinct from source-market opening range.
    The library's deterministic history/replay clock is always the brick time.
    """

    available_at: datetime | None = None
    day_open: float | None = None
    previous_close: float | None = None
    previous_high: float | None = None
    previous_low: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    flow_ok: bool = False
    flow_score: int = 0
    vwap_side: int = 0
    volume_side: int = 0

    def validate(self, brick: Brick) -> None:
        if self.available_at is not None and (
            self.available_at.utcoffset() is None or self.available_at > brick.ts
        ):
            raise ValueError("context is naive or unavailable at this brick")
        for name in (
            "day_open",
            "previous_close",
            "previous_high",
            "previous_low",
            "day_high",
            "day_low",
        ):
            value = getattr(self, name)
            if value is not None and (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError("invalid context price")
        for name, limit in (("flow_score", 5), ("vwap_side", 1), ("volume_side", 1)):
            value = getattr(self, name)
            if type(value) is not int or abs(value) > limit:
                raise ValueError("invalid flow context")
        if type(self.flow_ok) is not bool:
            raise ValueError("invalid flow availability")
        if self.available_at is None and (
            self.flow_ok
            or any(
                getattr(self, k) is not None
                for k in (
                    "day_open",
                    "previous_close",
                    "previous_high",
                    "previous_low",
                    "day_high",
                    "day_low",
                )
            )
        ):
            raise ValueError("source context availability timestamp required")

    @classmethod
    def from_market(
        cls, daily: dict[str, Any], at: datetime, flow: dict[str, Any] | None = None
    ) -> "PineContext":
        """Bridge accepted BE-08 daily/flow context without filling absent values."""
        fields = {
            dest: float(daily[src]) if daily.get(src) is not None else None
            for dest, src in (
                ("day_open", "open"),
                ("previous_close", "previous_close"),
                ("previous_high", "previous_high"),
                ("previous_low", "previous_low"),
                ("day_high", "high"),
                ("day_low", "low"),
            )
        }
        if flow:
            end = datetime.fromisoformat(flow["completed_at"])
            if end.utcoffset() is None or end > at:
                raise ValueError("future flow context")
        score = flow["score"] if flow else 0
        px = flow.get("price_pct") if flow else None
        vol = (
            (1 if px > 0 else -1 if px < 0 else 0)
            if flow and flow["volume_spike"] and px is not None
            else 0
        )
        return cls(
            available_at=at,
            **fields,
            flow_ok=bool(flow and flow["flow_ok"]),
            flow_score=score,
            vwap_side=flow["vwap_side"] if flow else 0,
            volume_side=vol,
        )

    def serializable(self) -> dict[str, Any]:
        return asdict(self) | {
            "available_at": self.available_at.isoformat() if self.available_at else None
        }


class PineEngine:
    def __init__(self, stream: str, settings: IndicatorSettings | None = None) -> None:
        self.base = IndicatorEngine(stream, settings)
        self.history: list[dict[str, Any]] = []

    def process(
        self, brick: Brick, context: PineContext | None = None
    ) -> dict[str, Any]:
        context = context or PineContext()
        context.validate(brick)
        working = copy.deepcopy(self)
        result = working._process(brick, context)
        # No partially advanced state if validation, rendering or calculation fails.
        self.base, self.history = working.base, working.history
        return result

    def _process(self, brick: Brick, context: PineContext) -> dict[str, Any]:
        old = copy.deepcopy(self.base.variables)
        previous = self.history[-1] if self.history else {}
        previous_rsi = self.base.previous_rsi
        today = brick.ts.astimezone(IST).date().isoformat()
        if today != self.base.day and not self.base.settings["divCrossDay"]:
            for name in (
                "lastTopP",
                "lastTopR",
                "lastTopI",
                "prevTopP",
                "lastBotP",
                "lastBotR",
                "lastBotI",
                "prevBotP",
            ):
                old[name] = None
        f = self.base.process(brick)
        clock = brick.ts.astimezone(IST)
        f.update({k: v for k, v in asdict(context).items() if k != "available_at"})
        f.update(
            open=float(brick.open),
            close=float(brick.close),
            high=float(brick.high),
            low=float(brick.low),
            time_ms=int(brick.ts.timestamp() * 1000),
            minute=clock.hour * 60 + clock.minute,
            is_up=f["direction"] < 0,
            previous_rsi=previous_rsi,
        )
        f["flow_ok"] = f["flow_ok"] and self.base.settings["flowOn"]
        if not f["flow_ok"]:
            f.update(flow_score=0, vwap_side=0, volume_side=0)
        v, s = self.base.variables, self.base.settings
        divergence(v, old, previous, f, s)
        outlook_bias(v, previous, f, s, self.history)
        raw = raw_signals(v, previous, f, s)
        signals = select_signals(raw, v, f, s)
        accepted = [x for x in signals if x["accepted"]]
        for sig in accepted:
            sig["explanation"] = explanation(sig, v, f, s)
            accept_signal(sig, v, f)
        events = trade_step(v, f, s, accepted)
        signal_statistics(v, f, s, accepted)
        f.update(last_top=v["lastTopP"], last_bottom=v["lastBotP"])
        # Only bounded series history is necessary; pending evaluation samples are
        # already retained in the Pine var arrays and persisted with the base.
        self.history = (self.history + [f])[-30:]
        result = {
            **f,
            "raw_signals": {str(k): value for k, value in raw.items()},
            "signals": signals,
            "events": events,
            "position": {
                key: v[key]
                for key in (
                    "posDir",
                    "posEntry",
                    "posStop",
                    "posT1",
                    "posT2",
                    "posBar",
                    "posT1Hit",
                    "posType",
                    "posGrade",
                    "posId",
                )
            },
            "statistics": {
                key: copy.deepcopy(v[key])
                for key in (
                    "cN",
                    "cW",
                    "cP",
                    "cB",
                    "cT1",
                    "cT2",
                    "trN",
                    "trW",
                    "trP",
                    "tN",
                    "tW",
                    "tP",
                    "gN",
                    "gW",
                    "gP",
                )
            },
            "mode": "INDICATOR_REPLAY",
            "schema_version": 1,
            "entries_enabled": False,
        }
        json.dumps(result, allow_nan=False)
        return copy.deepcopy(result)

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": 1,
            "base": self.base.snapshot(),
            "history": copy.deepcopy(self.history),
        }

    @classmethod
    def restore(
        cls, snapshot: dict[str, Any], stream: str, settings: IndicatorSettings
    ) -> "PineEngine":
        if snapshot.get("version") != 1:
            raise ValueError("unknown signal engine snapshot version")
        json.dumps(snapshot, allow_nan=False)
        engine = cls(stream, settings)
        engine.base = IndicatorEngine.restore(snapshot["base"], stream, settings)
        history = copy.deepcopy(snapshot["history"])
        if not isinstance(history, list) or len(history) != min(
            30, engine.base.last_index + 1
        ):
            raise ValueError("incomplete signal engine history")
        for offset, row in enumerate(history):
            if not isinstance(row, dict):
                raise ValueError("invalid signal engine history row")
            if row.get("index") != engine.base.last_index - len(history) + 1 + offset:
                raise ValueError("unordered signal engine history")
            for key in (
                "close",
                "rsi",
                "brick_direction",
                "bucket",
                "run_length",
                "time_ms",
                "flipped",
                "last_top",
                "last_bottom",
                "surge_L",
                "surge_S",
            ):
                if key not in row:
                    raise ValueError("signal engine history lacks required series")
            if (
                type(row["bucket"]) is not int
                or not 0 <= row["bucket"] < 12
                or type(row["run_length"]) is not int
                or row["run_length"] < 1
                or type(row["time_ms"]) is not int
                or row["brick_direction"] not in (-1, 0, 1)
                or any(
                    type(row[k]) is not bool for k in ("flipped", "surge_L", "surge_S")
                )
            ):
                raise ValueError("invalid signal history values")
            for key in ("close", "rsi", "last_top", "last_bottom"):
                value = row[key]
                if value is not None and (
                    type(value) not in (int, float) or not math.isfinite(value)
                ):
                    raise ValueError("invalid signal history price/RSI")
        arrays = [
            engine.base.variables[k] for k in ("pBar", "pPx", "pDir", "pTyp", "pGr")
        ]
        if len({len(a) for a in arrays}) != 1:
            raise ValueError("pending signal arrays disagree")
        v = engine.base.variables
        if (
            any(sd not in (-1, 1) for sd in v["pDir"])
            or any(not 0 <= t < 8 for t in v["pTyp"])
            or any(not 1 <= g <= 3 for g in v["pGr"])
        ):
            raise ValueError("invalid pending signal classification")
        if any(i > engine.base.last_index or i < 0 for i in v["pBar"]):
            raise ValueError("invalid pending signal brick")
        if v["posDir"] not in (-1, 0, 1):
            raise ValueError("invalid indicator position direction")
        if v["posDir"] and (
            v["posType"]
            not in ("CORE", "DIV", "HDIV", "PB", "BRK", "TRAP", "ORB", "SRG")
            or v["posEntry"] is None
            or v["posEntry"] <= 0
            or v["posBar"] is None
            or not 0 <= v["posBar"] <= engine.base.last_index
            or v["posT1"] is None
            or v["posT2"] is None
            or len(v["posId"]) != 7
        ):
            raise ValueError("invalid active indicator position")
        engine.history = history
        return engine
