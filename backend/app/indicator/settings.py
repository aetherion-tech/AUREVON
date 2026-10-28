"""Literal Pine input names/defaults; chart identity remains separately verified."""

import json
import math
from pathlib import Path
from typing import Any

INPUTS: dict[str, dict[str, Any]] = json.loads(
    Path(__file__).with_name("inputs.json").read_text()
)


class IndicatorSettings:
    def __init__(self, **overrides: Any) -> None:
        if overrides.keys() - INPUTS.keys():
            raise ValueError("unknown Pine input")
        self._values = {k: v["default"] for k, v in INPUTS.items()} | overrides
        for name, value in self._values.items():
            rule = INPUTS[name]
            kind = rule["kind"]
            valid = (
                type(value) is bool
                if kind == "bool"
                else type(value) is int
                if kind == "int"
                else type(value) in (int, float)
                if kind == "float"
                else isinstance(value, str) and bool(value)
            )
            if not valid:
                raise ValueError(f"invalid {name} type")
            if kind in ("int", "float"):
                if not math.isfinite(value) or not (
                    rule.get("minval", -math.inf)
                    <= value
                    <= rule.get("maxval", math.inf)
                ):
                    raise ValueError(f"invalid {name} bounds")
            if "options" in rule and value not in rule["options"]:
                raise ValueError(f"invalid {name} option")
        hhmm = self._values["orbUntil"]
        if hhmm % 100 >= 60:
            raise ValueError("invalid ORB HHMM")

    def __getitem__(self, name: str) -> Any:
        return self._values[name]

    @property
    def values(self) -> dict[str, Any]:
        return self._values.copy()
