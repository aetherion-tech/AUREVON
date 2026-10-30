"""Preserve a TradingView debug CSV and normalize only observed reference columns.

No reference acceptance, context synthesis, network calls or trading activation.
"""

import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.tools.reference_debug import FIELDS, ORIGINAL_SHA256

BASE = (
    "index",
    "time",
    "open",
    "high",
    "low",
    "close",
    "rsi",
    "supertrend",
    "direction",
)
ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789#@$%&*+!"


def decode_id(value: str) -> str:
    if not value:
        return ""
    number = Decimal(value)
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError("Trade ID code must be a finite integer")
    code = int(number)
    if not 0 <= code < 40**5:
        raise ValueError("Trade ID code is outside the original alphabet range")
    characters = []
    for _ in range(5):
        code, digit = divmod(code, 40)
        characters.append(ID_ALPHABET[digit])
    return "[" + "".join(reversed(characters)) + "]"


def timestamp(value: str) -> datetime:
    try:
        numeric = Decimal(value)
    except InvalidOperation:
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None:
            raise ValueError("Reference timestamps require explicit timezone offsets")
        return result
    if not numeric.is_finite():
        raise ValueError("Nonfinite reference timestamp")
    # TradingView can export Unix seconds or milliseconds; no index inference.
    return datetime.fromtimestamp(
        float(numeric / 1000 if abs(numeric) >= 100_000_000_000 else numeric),
        tz=timezone.utc,
    )


def normalize(raw: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    headers = reader.fieldnames or []
    expected = ["time", "open", "high", "low", "close"] + [
        f"ref_{name}" for name in FIELDS
    ]
    mapping = {}
    for name in expected:
        matches = [
            h
            for h in headers
            if h.strip().lower() == name or h.strip().lower().endswith(": " + name)
        ]
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous TradingView column: {name}")
        mapping[name] = matches[0]
    rows: list[dict[str, str]] = []
    previous: datetime | None = None
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Malformed CSV row")
        data = {name: row[source].strip() for name, source in mapping.items()}
        index = Decimal(data["ref_index"])
        if index != len(rows):
            raise ValueError("Export must start at bar_index 0; do not rebase or sort")
        if Decimal(data["ref_confirmed"]) != 1:
            raise ValueError(
                "Export contains an unconfirmed brick; re-export closed data"
            )
        at = timestamp(data["time"])
        if previous and at < previous:
            raise ValueError("Reference timestamps are out of order")
        previous = at
        prices = [Decimal(data[k]) for k in ("open", "high", "low", "close")]
        if any(not n.is_finite() or n <= 0 for n in prices):
            raise ValueError("Invalid reference OHLC")
        opening, high, low, close = prices
        if not low <= min(opening, close) <= max(opening, close) <= high:
            raise ValueError("Invalid reference OHLC ordering")
        result = {k: data[k] for k in ("open", "high", "low", "close")}
        result.update(index=str(len(rows)), time=at.isoformat())
        for name in FIELDS:
            text = data[f"ref_{name}"]
            if text.lower() in ("", "na", "nan"):
                result[name] = ""
            elif not Decimal(text).is_finite():
                raise ValueError(f"Nonfinite reference value: {name}")
            else:
                result[name] = text
        for field in ("active", "exit", "t1"):
            result[f"{field}_trade_id"] = decode_id(result[f"{field}_id"])
        # Canonicalize only the already-validated integer index representation.
        result["index"] = str(len(rows))
        rows.append(result)
    if not rows:
        raise ValueError("Empty TradingView export")
    return rows


def intake(source: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise ValueError("Choose a new output directory; prior evidence is immutable")
    raw = source.read_bytes()
    rows = normalize(raw)
    # All validation precedes creation. Never rewrite the source or parity values.
    output.mkdir(parents=True, exist_ok=False)
    (output / "original.csv").write_bytes(raw)
    for filename, columns in (
        ("math.csv", BASE),
        (
            "debug.csv",
            tuple(dict.fromkeys((*BASE, *FIELDS)))
            + ("active_trade_id", "exit_trade_id", "t1_trade_id"),
        ),
    ):
        with (output / filename).open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    report = {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "original_pine_sha256": ORIGINAL_SHA256,
        "rows": len(rows),
        "first": rows[0]["time"],
        "last": rows[-1]["time"],
        "reference_verified": False,
        "formal_sessions": 0,
        "limitations": [
            "Chart identity, input settings and ten exchange days not verified",
            "Independent spot/futures/OI/daily context and G1/G2 still required",
            "No full signals/events/context parity envelope synthesized",
            "Numeric trade IDs use the debug alphabet, never guessed sequence IDs",
        ],
        "files": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.iterdir())
        },
    }
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(intake(args.csv, args.output), indent=2))


if __name__ == "__main__":
    main()
