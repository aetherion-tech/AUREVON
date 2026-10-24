"""Strict CSV readers and deterministic price replay."""

import csv
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.market.renko_builder import Brick, RenkoBuilder


def read_rows(path: Path, required: set[str]) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing CSV header")
        names = [name.strip().lower() for name in reader.fieldnames]
        if len(names) != len(set(names)) or not required.issubset(names):
            raise ValueError(f"{path}: expected unique columns {sorted(required)}")
        reader.fieldnames = names
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}:{number}: malformed CSV row")
            yield {key: value.strip() for key, value in row.items()}


def replay(path: Path, builder: RenkoBuilder) -> list[Brick]:
    """Input time is ISO-8601 with offset; close is a completed candle close.

    In tick mode use price instead of close. Candle highs/lows are deliberately
    not replayed: their intraminute ordering is unknown.
    """
    column = "close" if builder.mode == "minute_close" else "price"
    bricks = []
    for row in read_rows(path, {"time", column}):
        bricks.extend(
            builder.on_price(row[column], datetime.fromisoformat(row["time"]))
        )
    return bricks


def reference_bricks(path: Path) -> list[tuple[Decimal, Decimal, int]]:
    result = []
    for row in read_rows(path, {"open", "close"}):
        opening, closing = Decimal(row["open"]), Decimal(row["close"])
        if not opening.is_finite() or not closing.is_finite() or opening == closing:
            raise ValueError("reference bricks must have finite, unequal open/close")
        result.append((opening, closing, 1 if closing > opening else -1))
    return result
