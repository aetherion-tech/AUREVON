"""Full indicator parity from debug CSV plus independently recorded source context.

Columns: index,time,open,high,low,close,rsi,supertrend,direction,bias_score,
bias_direction,flow_score,signals,events,context,futures. Last four use JSON.
Context contains daily input references/available_at, never computed flow values.
Futures is a JSON array of newly completed exact-contract bars (start/end/high/
low/close/volume/oi) plus contract, previous_close and previous_oi per item.
Omitted futures means genuinely unavailable flow, never reference-output input.
"""

import csv
import hashlib
import json
import math
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.indicator.flow import FlowBar, FuturesFlow
from app.indicator.settings import IndicatorSettings
from app.indicator.strategy import PineContext, PineEngine
from app.market.renko_builder import IST, Brick

SIGNAL_KEYS = ("type", "direction", "grade", "accepted", "reason")
EVENT_KEYS = ("kind", "trade_id", "type", "direction", "price")


def projection(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: result[key]
        for key in (
            "rsi",
            "supertrend",
            "direction",
            "bias_score",
            "bias_direction",
            "flow_score",
        )
    } | {
        "signals": [
            {key: sig[key] for key in SIGNAL_KEYS} for sig in result["signals"]
        ],
        "events": [
            {key: event.get(key) for key in EVENT_KEYS} for event in result["events"]
        ],
    }


def first_difference(
    expected: Any, actual: Any, tolerance: float, path: str = ""
) -> dict[str, Any] | None:
    if (
        isinstance(expected, dict)
        and isinstance(actual, dict)
        and expected.keys() == actual.keys()
    ):
        for key in expected:
            mismatch = first_difference(
                expected[key], actual[key], tolerance, f"{path}.{key}" if path else key
            )
            if mismatch:
                return mismatch
        return None
    if (
        isinstance(expected, list)
        and isinstance(actual, list)
        and len(expected) == len(actual)
    ):
        for index, (a, b) in enumerate(zip(expected, actual)):
            mismatch = first_difference(a, b, tolerance, f"{path}[{index}]")
            if mismatch:
                return mismatch
        return None
    if type(expected) in (int, float) and type(actual) in (int, float):
        if not math.isfinite(expected) or not math.isfinite(actual):
            raise ValueError("nonfinite parity value")
        # Grades, flags, directions and counters are exact; tolerance only for
        # measured continuous values, including an event's price.
        allowed = (
            tolerance
            if path.rsplit(".", 1)[-1] in ("rsi", "supertrend", "price")
            else 0
        )
        if abs(expected - actual) <= allowed:
            return None
    elif type(expected) is type(actual) and expected == actual:
        return None
    return {"column": path, "expected": expected, "actual": actual}


def compare_full(
    path: Path,
    settings: IndicatorSettings,
    tolerance: float = 1e-8,
    required_days: int = 1,
) -> dict[str, Any]:
    if not math.isfinite(tolerance) or tolerance < 0 or required_days < 1:
        raise ValueError("invalid parity tolerance/day requirement")
    engine = PineEngine("parity", settings)
    flow: FuturesFlow | None = None
    latest_flow: dict[str, Any] | None = None
    dates: set[str] = set()
    count = 0
    provenance = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "settings": settings.values,
        "tolerance": tolerance,
    }
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        columns = {
            "index",
            "time",
            "open",
            "high",
            "low",
            "close",
            "rsi",
            "supertrend",
            "direction",
            "bias_score",
            "bias_direction",
            "flow_score",
            "signals",
            "events",
            "context",
            "futures",
        }
        if not columns <= set(reader.fieldnames or []):
            raise ValueError("missing full debug columns")
        for row in reader:
            time = datetime.fromisoformat(row["time"])
            opening, close = Decimal(row["open"]), Decimal(row["close"])
            if Decimal(row["high"]) != max(opening, close) or Decimal(
                row["low"]
            ) != min(opening, close):
                raise ValueError(
                    "full engine requires body-only Renko OHLC; "
                    "wick parity is unavailable"
                )
            brick = Brick(
                int(row["index"]),
                opening,
                close,
                1 if close > opening else -1 if close < opening else 0,
                time,
            )
            daily = json.loads(row["context"] or "{}")
            if {"flow_ok", "flow_score", "vwap_side", "volume_side"} & daily.keys():
                raise ValueError(
                    "flow must be computed from independent futures inputs"
                )
            context_time = daily.pop("available_at", None)
            if daily and context_time is None:
                raise ValueError("daily context requires source availability")
            # A fresh per-brick envelope names its point-in-time availability.
            daily_context = PineContext(
                **daily,
                available_at=datetime.fromisoformat(context_time)
                if context_time
                else None,
            )
            daily_context.validate(brick)
            for item in json.loads(row["futures"] or "[]"):
                contract = item["contract"]
                if flow is None:
                    flow = FuturesFlow(contract, settings)
                bar = FlowBar(
                    datetime.fromisoformat(item["start"]),
                    datetime.fromisoformat(item["end"]),
                    *(item[k] for k in ("high", "low", "close", "volume", "oi")),
                )
                latest_flow = flow.update(
                    bar,
                    time,
                    contract,
                    item.get("previous_close"),
                    item.get("previous_oi"),
                )
            if latest_flow:
                px = latest_flow["price_pct"]
                vol = (
                    (1 if px > 0 else -1 if px < 0 else 0)
                    if latest_flow["volume_spike"] and px is not None
                    else 0
                )
                daily_context = PineContext(
                    **daily,
                    available_at=daily_context.available_at or time,
                    flow_ok=latest_flow["flow_ok"],
                    flow_score=latest_flow["score"],
                    vwap_side=latest_flow["vwap_side"],
                    volume_side=vol,
                )
            result = engine.process(brick, daily_context)
            want = {}
            for key in (
                "rsi",
                "supertrend",
                "direction",
                "bias_score",
                "bias_direction",
                "flow_score",
            ):
                text = row[key].strip().lower()
                want[key] = None if text in ("", "na", "nan") else float(text)
            want["signals"] = json.loads(row["signals"])
            want["events"] = json.loads(row["events"])
            mismatch = first_difference(want, projection(result), tolerance)
            if mismatch:
                return {
                    "passed": False,
                    "index": brick.index,
                    **mismatch,
                    "provenance": provenance,
                }
            dates.add(time.astimezone(IST).date().isoformat())
            count += 1
    if not count:
        raise ValueError("empty full debug export")
    return {
        "passed": len(dates) >= required_days,
        "bricks": count,
        "days": sorted(dates),
        "required_days": required_days,
        "reason": "matched"
        if len(dates) >= required_days
        else "insufficient_reference_days",
        "provenance": provenance,
    }
