"""Ordered completed-brick context. No signals, fills, or live worker activation."""

import copy
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from app.indicator.math import RSI, BarsSince, Supertrend
from app.indicator.settings import IndicatorSettings
from app.market.lifecycle_state import LifecycleStore
from app.market.renko_builder import IST, Brick
from app.market.session_context import session_context
from app.market.warmup import SessionCalendar

VARIABLES: dict[str, dict[str, Any]] = json.loads(
    Path(__file__).with_name("variables.json").read_text()
)


class IndicatorEngine:
    """Single stream/replay owner; persist snapshots explicitly after processing.

    An initial stream starts at index zero. Equal-time bricks remain ordered by
    index. Gaps, duplicate events, wrong OHLC and backward timestamps fail before
    mutation. Feed only committed Brick instances from the market pipeline.
    """

    def __init__(self, stream: str, settings: IndicatorSettings | None = None) -> None:
        if not stream:
            raise ValueError("stream identity required")
        self.stream = stream
        self.settings = settings or IndicatorSettings()
        self.rsi = RSI(self.settings["rsiLen"])
        self.st = Supertrend(self.settings["atrLen"], self.settings["factor"])
        self.since = BarsSince()
        self.variables = {k: copy.deepcopy(v["initial"]) for k, v in VARIABLES.items()}
        self.last_index = -1
        self.last_time: datetime | None = None
        self.previous_close: float | None = None
        self.previous_rsi: float | None = None
        self.previous_color = 0
        self.previous_direction: int | None = None
        self.day: str | None = None

    def process(self, brick: Brick) -> dict[str, Any]:
        if brick.index != self.last_index + 1:
            raise ValueError("duplicate, missing or out-of-order brick index")
        if brick.ts.tzinfo is None or brick.ts.utcoffset() is None:
            raise ValueError("aware brick timestamp required")
        if self.last_time is not None and brick.ts < self.last_time:
            raise ValueError("backward brick timestamp")
        o, c = float(brick.open), float(brick.close)
        color = 1 if c > o else -1 if c < o else 0
        if not all(math.isfinite(v) and v > 0 for v in (o, c)):
            raise ValueError("invalid brick price")
        if brick.direction != color:
            raise ValueError("brick direction disagrees with OHLC")
        day = brick.ts.astimezone(IST).date().isoformat()
        v = self.variables
        if day != self.day:
            for name in (
                "sigToday",
                "orH",
                "orL",
                "orbUpSeen",
                "orbDnSeen",
                "trapUpBar",
                "trapDnBar",
                "srgArmL",
                "srgArmS",
            ):
                v[name] = copy.deepcopy(VARIABLES[name]["initial"])
            if not self.settings["divCrossDay"]:
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
                    v[name] = None
        rsi = self.rsi.update(c)
        st, direction = self.st.update(float(brick.high), float(brick.low), c)
        flipped = (
            self.previous_direction is not None and direction != self.previous_direction
        )
        bsf = self.since.update(flipped)
        run = v["runLen"] + 1 if color != 0 and color == self.previous_color else 1
        if self.previous_color == 1 and color == -1:
            v["prevTopP"] = v["lastTopP"]
            v["lastTopP"], v["lastTopR"], v["lastTopI"] = (
                self.previous_close,
                self.previous_rsi,
                brick.index - 1,
            )
        if self.previous_color == -1 and color == 1:
            v["prevBotP"] = v["lastBotP"]
            v["lastBotP"], v["lastBotR"], v["lastBotI"] = (
                self.previous_close,
                self.previous_rsi,
                brick.index - 1,
            )
        v["runLen"] = run
        if c != o:
            v["lastBrickSz"] = abs(c - o)
        if v["firstTime"] is None:
            v["firstTime"] = int(brick.ts.timestamp() * 1000)
            v["idSalt"] = int(brick.ts.timestamp()) % 102400000
        self.last_index, self.last_time, self.day = brick.index, brick.ts, day
        self.previous_close, self.previous_rsi = c, rsi
        self.previous_color, self.previous_direction = color, direction
        return {
            "index": brick.index,
            "rsi": rsi,
            "atr": self.st.atr.value,
            "supertrend": st,
            "direction": direction,
            "flipped": flipped,
            "brick_direction": color,
            "run_length": run,
            "bars_since_flip": 99 if bsf is None else bsf,
            "trend_age": (99 if bsf is None else bsf) + 1,
            "top": {
                "price": v["lastTopP"],
                "rsi": v["lastTopR"],
                "index": v["lastTopI"],
                "age": None if v["lastTopI"] is None else brick.index - v["lastTopI"],
            },
            "bottom": {
                "price": v["lastBotP"],
                "rsi": v["lastBotR"],
                "index": v["lastBotI"],
                "age": None if v["lastBotI"] is None else brick.index - v["lastBotI"],
            },
        }

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(
            {
                "version": 1,
                "stream": self.stream,
                "settings": self.settings.values,
                "variables": self.variables,
                "last_index": self.last_index,
                "last_time": self.last_time.isoformat() if self.last_time else None,
                "previous_close": self.previous_close,
                "previous_rsi": self.previous_rsi,
                "previous_color": self.previous_color,
                "previous_direction": self.previous_direction,
                "day": self.day,
                "since": self.since.value,
                "rsi": {
                    "previous": self.rsi.previous,
                    "gain": vars(self.rsi.gain),
                    "loss": vars(self.rsi.loss),
                },
                "st": {**vars(self.st), "atr": vars(self.st.atr)},
            }
        )

    @classmethod
    def restore(
        cls, payload: dict[str, Any], stream: str, settings: IndicatorSettings
    ) -> "IndicatorEngine":
        p = copy.deepcopy(payload)
        if p.get("version") != 1 or p.get("stream") != stream:
            raise ValueError("snapshot version/stream mismatch")
        if (
            p.get("settings") != settings.values
            or p.get("variables", {}).keys() != VARIABLES.keys()
        ):
            raise ValueError("snapshot settings/variable inventory mismatch")
        # Reject non-JSON state and non-finite numbers before assigning anything.
        json.dumps(p, allow_nan=False)
        validate_snapshot(p, settings)
        engine = cls(stream, settings)
        for name in (
            "variables",
            "last_index",
            "previous_close",
            "previous_rsi",
            "previous_color",
            "previous_direction",
            "day",
        ):
            setattr(engine, name, p[name])
        engine.last_time = (
            datetime.fromisoformat(p["last_time"]) if p["last_time"] else None
        )
        if engine.last_time is not None and engine.last_time.utcoffset() is None:
            raise ValueError("snapshot timestamp must be aware")
        engine.since.value = p["since"]
        engine.rsi.previous = p["rsi"]["previous"]
        for name in ("gain", "loss"):
            target = getattr(engine.rsi, name)
            state = p["rsi"][name]
            if state["length"] != settings["rsiLen"]:
                raise ValueError("RSI snapshot length mismatch")
            target.seed, target.value = state["seed"], state["value"]
        for name in ("factor", "previous", "upper", "lower", "line", "direction"):
            setattr(engine.st, name, p["st"][name])
        if (
            p["st"]["atr"]["length"] != settings["atrLen"]
            or engine.st.factor != settings["factor"]
        ):
            raise ValueError("Supertrend snapshot configuration mismatch")
        engine.st.atr.seed = p["st"]["atr"]["seed"]
        engine.st.atr.value = p["st"]["atr"]["value"]
        return engine

    def save(self, store: LifecycleStore) -> None:
        store.write(f"indicator:{self.stream}", self.snapshot())

    def context(
        self, store: LifecycleStore, spot: int, calendar: SessionCalendar, brick: Brick
    ) -> dict[str, Any]:
        """Source context uses committed minute bars ending no later than the brick."""
        return session_context(store.engine, self.stream, spot, calendar, brick.ts)


def validate_snapshot(p: dict[str, Any], settings: IndicatorSettings) -> None:
    """Fail closed on damaged checkpoints, including nested smoothing state."""

    def number(value: Any, nullable: bool = True) -> bool:
        return (nullable and value is None) or (
            type(value) in (int, float) and math.isfinite(value)
        )

    try:
        if type(p["last_index"]) is not int or p["last_index"] < -1:
            raise ValueError("invalid checkpoint index")
        if (p["last_index"] == -1) != (p["last_time"] is None):
            raise ValueError("checkpoint time/index mismatch")
        if p["previous_color"] not in (-1, 0, 1) or p["previous_direction"] not in (
            None,
            -1,
            1,
        ):
            raise ValueError("invalid checkpoint direction")
        for name, spec in VARIABLES.items():
            value = p["variables"][name]
            kind = spec["type"]
            if spec["presentation_only"]:
                valid = value is None
            elif kind in ("float", "int"):
                valid = number(value) and (
                    value is None or kind == "float" or type(value) is int
                )
            elif kind == "bool":
                valid = type(value) is bool
            elif kind == "string":
                valid = isinstance(value, str)
            else:
                valid = isinstance(value, list)
                if valid:
                    subtype = kind[6:-1]
                    valid = all(
                        isinstance(x, str)
                        if subtype == "string"
                        else number(x, False) and (subtype != "int" or type(x) is int)
                        for x in value
                    )
                    initial = spec["initial"]
                    if initial:
                        valid = valid and len(value) == len(initial)
            if not valid:
                raise ValueError(f"invalid Pine state: {name}")
        for smooth, length in (
            (p["rsi"]["gain"], settings["rsiLen"]),
            (p["rsi"]["loss"], settings["rsiLen"]),
            (p["st"]["atr"], settings["atrLen"]),
        ):
            if (
                smooth["length"] != length
                or not number(smooth["value"])
                or not isinstance(smooth["seed"], list)
                or len(smooth["seed"]) >= length
                or not all(number(x, False) and x >= 0 for x in smooth["seed"])
                or (
                    smooth["value"] is not None
                    and (smooth["value"] < 0 or smooth["seed"])
                )
            ):
                raise ValueError("invalid smoothing state")
        for value in (
            p["previous_close"],
            p["previous_rsi"],
            p["rsi"]["previous"],
            *(p["st"][k] for k in ("previous", "upper", "lower", "line")),
        ):
            if not number(value):
                raise ValueError("invalid numerical checkpoint")
        if p["since"] is not None and (type(p["since"]) is not int or p["since"] < 0):
            raise ValueError("invalid flip age")
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("incomplete indicator checkpoint") from error
