"""First-divergence comparison for aligned TradingView debug OHLC exports.

Required columns: index,time,open,high,low,close,rsi,supertrend,direction.
Empty or 'na' output cells represent Pine warm-up. Compare complete history from
the same seed/start and configuration; a truncated export cannot prove parity.
"""

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from app.indicator.math import RSI, Supertrend
from app.indicator.settings import IndicatorSettings


def compare(
    path: Path, settings: IndicatorSettings, tolerance: float = 1e-8
) -> dict[str, Any]:
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("finite nonnegative absolute tolerance required")
    rsi = RSI(settings["rsiLen"])
    st = Supertrend(settings["atrLen"], settings["factor"])
    count = 0
    previous_time: datetime | None = None
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {
            "index",
            "time",
            "open",
            "high",
            "low",
            "close",
            "rsi",
            "supertrend",
            "direction",
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError("missing debug columns")
        for row in reader:
            index = int(row["index"])
            time = datetime.fromisoformat(row["time"])
            if (
                index != count
                or time.utcoffset() is None
                or (previous_time and time < previous_time)
            ):
                raise ValueError(
                    "debug export must start at zero with ordered aware timestamps"
                )
            o, h, low, c = (float(row[k]) for k in ("open", "high", "low", "close"))
            if (
                not all(math.isfinite(x) for x in (o, h, low, c))
                or not 0 < low <= min(o, c) <= max(o, c) <= h
            ):
                raise ValueError("invalid debug OHLC")
            line, direction = st.update(h, low, c)
            actual = {"rsi": rsi.update(c), "supertrend": line, "direction": direction}
            for column, value in actual.items():
                text = row[column].strip().lower()
                expected = None if text in ("", "na", "nan") else float(text)
                if expected is not None and not math.isfinite(expected):
                    raise ValueError("non-finite debug value")
                if (expected is None) != (value is None) or (
                    expected is not None
                    and value is not None
                    and abs(expected - value)
                    > (0 if column == "direction" else tolerance)
                ):
                    return {
                        "passed": False,
                        "index": index,
                        "column": column,
                        "expected": expected,
                        "actual": value,
                        "tolerance": tolerance,
                    }
            count += 1
            previous_time = time
    if not count:
        raise ValueError("empty debug export")
    return {"passed": True, "bricks": count, "tolerance": tolerance}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument(
        "--settings", type=Path, help="JSON mapping of literal Pine inputs"
    )
    parser.add_argument("--tolerance", type=float, default=1e-8)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Compare signals/trades and independent futures context",
    )
    parser.add_argument("--required-days", type=int, default=1)
    parser.add_argument(
        "--report", type=Path, help="Retain JSON first-divergence/provenance report"
    )
    args = parser.parse_args()
    import json

    settings = IndicatorSettings(
        **json.loads(args.settings.read_text()) if args.settings else {}
    )
    if args.full:
        from app.indicator.full_parity import compare_full

        result = compare_full(args.csv, settings, args.tolerance, args.required_days)
    else:
        result = compare(args.csv, settings, args.tolerance)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
