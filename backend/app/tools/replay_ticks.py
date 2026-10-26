"""Replay a complete recording run in exact event order without broker access."""

import argparse
import json
import sys
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.broker.kite_ticker import TickerWorker
from app.market.persistence import restore_builder


def timestamp(value: Any) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Recording timestamp requires a timezone")
    return result


def replay_events(paths: list[Path]) -> Iterator[dict[str, Any]]:
    """Stream results, retaining bounded worker state rather than a full day in RAM."""
    worker: TickerWorker | None = None
    session = None
    sequence = 0
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict) or event.get("version") != 1:
                        raise ValueError("Unsupported recording version")
                    if event["sequence"] != sequence:
                        raise ValueError("Recording sequence missing or out of order")
                    if worker is None:
                        session = event["session"]
                        worker = TickerWorker(
                            None, event["spot_token"], event["future_token"]
                        )
                    if (
                        event["session"] != session
                        or [event["spot_token"], event["future_token"]] != worker.tokens
                    ):
                        raise ValueError(
                            "Mixed recording sessions or instrument tokens"
                        )
                    at = timestamp(event["at"])
                    if event["kind"] == "checkpoint":
                        if sequence != 0:
                            raise ValueError("Checkpoint must be the first event")
                        state = event["checkpoint"]
                        if state["version"] != 1:
                            raise ValueError("Unknown checkpoint version")
                        for token in worker.tokens:
                            restore_builder(
                                worker.candles[token], state["builders"][str(token)]
                            )
                            worker.candle_counts[token] = state["counts"][str(token)]
                        worker.gap_required = state["gap"]
                        worker.gaps.restore(state.get("gaps", []))
                        sequence += 1
                        continue
                    if not isinstance(event["gap"], bool):
                        raise ValueError("Invalid gap marker")
                    worker.gap_required = event["gap"]
                    if "gaps" in event:
                        worker.gaps.restore(event["gaps"])
                    before = worker.candle_counts.copy()
                    if event["kind"] == "tick":
                        previous_invalid = worker.invalid
                        worker._accept(
                            {
                                "instrument_token": event["token"],
                                "exchange_timestamp": timestamp(event["exchange_time"]),
                                "last_price": event["price"],
                                "volume_traded": event["volume"],
                                "oi": event["oi"],
                            },
                            at,
                        )
                        if worker.invalid != previous_invalid:
                            raise ValueError("Recorded tick failed validation")
                    elif event["kind"] == "gap":
                        worker.gaps.restore(event["gaps"])
                        for builder in worker.candles.values():
                            builder.mark_gap()
                    elif event["kind"] == "advance":
                        worker.advance_candles(at)
                    else:
                        raise ValueError("Unknown recording event")
                    for token in worker.tokens:
                        count = worker.candle_counts[token] - before[token]
                        if count:
                            for candle in list(worker.closed_candles[token])[-count:]:
                                yield {"token": token, "candle": asdict(candle)}
                    sequence += 1
                except (ValueError, KeyError, TypeError, OverflowError) as error:
                    raise ValueError(
                        f"{path.name}:{line_number}: invalid recording ({error})"
                    ) from None
    if worker is None:
        raise ValueError("Recording is empty")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files", type=Path, nargs="+", help="Daily files in recorded order"
    )
    args = parser.parse_args(argv)
    try:
        for result in replay_events(args.files):
            print(json.dumps(result, default=str, sort_keys=True))
    except (OSError, ValueError) as error:
        print(f"Replay failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
