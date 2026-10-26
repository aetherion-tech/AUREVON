"""Validated historical candles with conservative 30-day request chunks."""

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, Protocol

from app.broker.kite_auth import IST


class HistoricalClient(Protocol):
    def historical_data(
        self,
        instrument_token: int,
        interval: str,
        start: datetime,
        end: datetime,
        *,
        oi: bool = False,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Candle:
    time: datetime  # Exchange candle opening time.
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    oi: Decimal | None


def parse_candle(row: Any, *, oi: bool, allow_missing_oi: bool = False) -> Candle:
    try:
        if oi and allow_missing_oi and isinstance(row, list):
            if len(row) == 6 or (len(row) == 7 and row[6] is None):
                return parse_candle(row[:6], oi=False)
        if not isinstance(row, list) or len(row) != (7 if oi else 6):
            raise ValueError
        ts = datetime.fromisoformat(row[0])
        numbers = [Decimal(str(value)) for value in row[1:]]
        if ts.tzinfo is None or any(not n.is_finite() for n in numbers):
            raise ValueError
        opening, high, low, closing, volume = numbers[:5]
        if (
            min(opening, high, low, closing) <= 0
            or volume < 0
            or low > min(opening, closing)
            or high < max(opening, closing)
            or (oi and numbers[5] < 0)
        ):
            raise ValueError
        return Candle(
            ts.astimezone(IST),
            opening,
            high,
            low,
            closing,
            volume,
            numbers[5] if oi else None,
        )
    except (ValueError, TypeError, InvalidOperation, IndexError):
        raise ValueError("Kite returned an invalid historical candle") from None


def download(
    auth: HistoricalClient,
    token: int,
    start: datetime,
    end: datetime,
    *,
    interval: Literal["minute", "5minute"] = "minute",
    oi: bool = False,
    now: datetime | None = None,
    allow_missing_oi: bool = False,
) -> list[Candle]:
    """Fetch an inclusive opening-time range; exclude unfinished candles.

    Overlapping chunk boundaries are deduplicated, conflicting copies rejected.
    Empty responses are valid (weekends/holidays); no prices are fabricated.
    """
    if any(t.tzinfo is None for t in (start, end)) or start > end:
        raise ValueError("Use timezone-aware start/end in chronological order")
    if token <= 0 or interval not in {"minute", "5minute"}:
        raise ValueError("Expected positive token and minute/5minute interval")
    cutoff = now if now is not None else datetime.now(IST)
    if cutoff.tzinfo is None:
        raise ValueError("now must include a timezone")
    duration = timedelta(minutes=1 if interval == "minute" else 5)
    finish = min(end, cutoff - duration)
    cursor = start
    candles: dict[datetime, Candle] = {}
    while cursor <= finish:
        boundary = min(cursor + timedelta(days=30), finish)
        data = auth.historical_data(token, interval, cursor, boundary, oi=oi)
        rows = data.get("candles")
        if not isinstance(rows, list):
            raise ValueError("Kite returned invalid historical data")
        for row in rows:
            candle = parse_candle(row, oi=oi, allow_missing_oi=allow_missing_oi)
            if not cursor <= candle.time <= boundary:
                raise ValueError("Kite returned a candle outside the requested range")
            if candle.time in candles and candles[candle.time] != candle:
                raise ValueError("Conflicting historical candles at the same time")
            candles[candle.time] = candle
        if boundary == finish:
            break
        cursor = boundary
    return sorted(candles.values(), key=lambda c: c.time)


def save_csv(path: Path, candles: list[Candle], interval: str) -> None:
    """Atomically export completed-close timestamps compatible with replay."""
    duration = timedelta(minutes=1 if interval == "minute" else 5)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "oi",
                    "candle_open_time",
                    "interval",
                ]
            )
            for c in candles:
                writer.writerow(
                    [
                        (c.time + duration).isoformat(),
                        c.open,
                        c.high,
                        c.low,
                        c.close,
                        c.volume,
                        c.oi,
                        c.time.isoformat(),
                        interval,
                    ]
                )
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
