"""Review retained actual feed samples without broker access or operator writes.

Stale/delay states are reconstructed at recorded event times, never described as
captured socket status. This is not a new live session or formal burn-in.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.broker.kite_ticker import TickerWorker
from app.config import BACKEND_DIR
from app.market.exchange_calendar import ExchangeCalendar
from app.tools.replay_ticks import replay_events, timestamp


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            result.update(block)
    return result.hexdigest()


def historical_rows(path: Path) -> dict[datetime, dict[str, Any]]:
    rows: dict[datetime, dict[str, Any]] = {}
    weighted, volume = Decimal(0), Decimal(0)
    previous: datetime | None = None
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            opening, end = timestamp(row["candle_open_time"]), timestamp(row["time"])
            if opening in rows or end <= opening or (previous and opening <= previous):
                raise ValueError("Historical times duplicate or invalid")
            previous = opening
            data: dict[str, Any] = {
                key: Decimal(row[key]) if row[key] else None
                for key in ("open", "high", "low", "close", "volume", "oi")
            }
            if any(
                value is not None and not value.is_finite() for value in data.values()
            ):
                raise ValueError("Nonfinite historical value")
            if data["volume"]:
                weighted += (
                    (data["high"] + data["low"] + data["close"]) / 3 * data["volume"]
                )
                volume += data["volume"]
            data.update(
                end=end, bar_hlc3_session_vwap=weighted / volume if volume else None
            )
            rows[opening] = data
    return rows


def review(
    paths: list[Path],
    spot_csv: Path,
    future_csv: Path,
    history_receipt: Path,
) -> dict[str, Any]:
    if not paths:
        raise ValueError("Recording paths required")
    source_hashes = {str(path): digest(path) for path in paths}
    provenance = json.loads(history_receipt.read_text(encoding="utf-8"))
    if provenance.get("status") != "PASS":
        raise ValueError("Accepted actual historical-download receipt required")
    for label, path in (("spot", spot_csv), ("future", future_csv)):
        if digest(path) != provenance[label]["csv_sha256"]:
            raise ValueError("Historical source hash changed")
    with paths[0].open(encoding="utf-8") as stream:
        first = json.loads(next(stream))
    tokens = [first["spot_token"], first["future_token"]]
    if tokens != [provenance["spot"]["token"], provenance["future"]["token"]]:
        raise ValueError("Historical and recorded instrument identities differ")
    clock = timestamp(first["at"])
    calendar = ExchangeCalendar(BACKEND_DIR / "app/market/calendars").window(clock)
    worker = TickerWorker(None, *tokens, calendar=calendar)
    counts: Counter[str] = Counter()
    tick_counts: Counter[int] = Counter()
    quality: Counter[str] = Counter()
    quality["recorded_gap_flagged_events"] = 0
    previous: datetime | None = None
    first_tick: datetime | None = None
    last_tick: datetime | None = None
    event_time_regressions: list[dict[str, Any]] = []

    def observe(current: TickerWorker, event: dict[str, Any]) -> None:
        nonlocal previous, first_tick, last_tick
        at = timestamp(event["at"])
        if previous is not None and at < previous:
            # Capture times may regress across event kinds. Preserve sequence;
            # report every regression rather than sorting or hiding it.
            event_time_regressions.append(
                {
                    "sequence": event["sequence"],
                    "kind": event["kind"],
                    "delta_ms": (at - previous).total_seconds() * 1000,
                }
            )
        previous = at
        counts[event["kind"]] += 1
        if event.get("gap"):
            quality["recorded_gap_flagged_events"] += 1
        current.clock = lambda: at
        status = current.status()
        for key in ("stale", "clock_or_feed_delay", "session_expected"):
            quality[f"reconstructed_{key}_events"] += int(status[key])
        if event["kind"] == "tick":
            tick_counts[event["token"]] += 1
            first_tick = first_tick or at
            last_tick = at

    candles = list(replay_events(paths, worker=worker, on_event=observe))
    # A second independent replay must produce identical completed candles.
    independent = TickerWorker(None, *tokens, calendar=calendar)
    if candles != list(replay_events(paths, worker=independent)):
        raise ValueError("Independent recorded candle replay disagrees")
    histories = {
        tokens[0]: historical_rows(spot_csv),
        tokens[1]: historical_rows(future_csv),
    }
    comparisons = []
    for item in candles:
        token, candle = item["token"], item["candle"]
        expected = histories[token].get(candle["time"])
        if expected is None or expected["end"] != candle["end"]:
            raise ValueError("Recorded candle has no aligned historical counterpart")
        deltas = {
            key: candle[key] - expected[key]
            if candle[key] is not None and expected[key] is not None
            else None
            for key in ("open", "high", "low", "close", "volume", "oi")
        }
        history_vwap = expected["bar_hlc3_session_vwap"]
        vwap_available = candle["vwap"] is not None and history_vwap is not None
        vwap_reason = (
            "Retained sample starts mid-session; historical VWAP "
            "has earlier session volume"
            if candle["vwap_partial"]
            else "Same completed-session HLC3-volume basis"
        )
        if not vwap_available:
            vwap_reason = "VWAP unavailable without a valid volume basis"
        comparisons.append(
            {
                "token": token,
                "time": candle["time"],
                "end": candle["end"],
                "partial": candle["partial"],
                "vwap_partial": candle["vwap_partial"],
                "live_sample": candle,
                "historical": expected,
                "live_minus_historical": deltas,
                "vwap_comparable": vwap_available and not candle["vwap_partial"],
                "vwap_delta": candle["vwap"] - history_vwap if vwap_available else None,
                "vwap_reason": vwap_reason,
            }
        )
    if {str(path): digest(path) for path in paths} != source_hashes:
        raise ValueError(
            "Recording changed during review; use a quiescent retained file"
        )
    for label, path in (("spot", spot_csv), ("future", future_csv)):
        if digest(path) != provenance[label]["csv_sha256"]:
            raise ValueError("Historical source changed during review")
    return {
        "evidence": (
            "RETAINED_REAL_FEED_SAMPLE_REVIEW"
            if provenance.get("evidence") == "ACTUAL_AUTHENTICATED_KITE_HISTORICAL"
            else "SYNTHETIC_RECORDED_REVIEW_ONLY"
        ),
        "source_hashes": source_hashes,
        "source_events": sum(counts.values()),
        "event_kinds": dict(counts),
        "ticks_by_token": dict(tick_counts),
        "first_tick_at": first_tick,
        "last_tick_at": last_tick,
        "quality": dict(quality),
        "connected_at_capture": None,
        "queue_drops_at_capture": None,
        "reconnects_at_capture": None,
        "quality_note": (
            "Stale/delay reconstructed at recorded event times; "
            "socket status not captured"
        ),
        "event_time_regressions": event_time_regressions,
        "deterministic_completed_candles": True,
        "completed_candles": len(candles),
        "comparisons": comparisons,
        "unfinished_tail": {
            token: {"time": builder.current.time, "end": builder.current.end}
            for token, builder in worker.candles.items()
            if builder.current is not None
        },
        "formal_sessions": 0,
        "g1_accepted": False,
        "g2_accepted": False,
        "operator_state_changed": False,
        "broker_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", type=Path, nargs="+", required=True)
    parser.add_argument("--spot-csv", type=Path, required=True)
    parser.add_argument("--future-csv", type=Path, required=True)
    parser.add_argument("--history-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = review(
        args.recording, args.spot_csv, args.future_csv, args.history_receipt
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, default=str, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "comparisons"},
            default=str,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
