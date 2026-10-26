"""Explicit tick-mode rebuild from a complete, gap-free ordered recording."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.market.renko_builder import Brick, RenkoBuilder
from app.market.warmup import SessionCalendar, local_time


class TickFidelityError(RuntimeError):
    """Tick ordering cannot be reconstructed from minute candles or partial files."""

    rebuild_required = True


@dataclass(frozen=True)
class TickRestoreResult:
    renko: RenkoBuilder
    bricks: tuple[Brick, ...]
    samples: int
    source_run: str
    fidelity: Literal["recorded_order_only"] = "recorded_order_only"
    entries_enabled: Literal[False] = False


def restore_tick_renko(
    paths: list[Path],
    *,
    box: float | str,
    anchor: float | str,
    calendar: SessionCalendar,
    ordering_complete: bool = False,
) -> TickRestoreResult:
    """Full-run rebuild only; never merge a minute-close checkpoint into tick mode.

    Caller must attest complete captured ordering and freeze all source files.
    Even a valid recording cannot establish unobserved exchange tick ordering or
    TradingView parity. Same-time samples retain recording sequence, never sorting.
    """
    from app.tools.replay_ticks import replay_events, timestamp

    if ordering_complete is not True:
        raise TickFidelityError(
            "Tick ordering unavailable; explicit complete recording or rebuild required"
        )
    renko = RenkoBuilder(box, anchor, mode="tick")
    bricks: list[Brick] = []
    samples = 0
    run = ""
    try:
        # Validate all files before exposing any rebuilt state.
        for _ in replay_events(paths):
            pass
        for path in paths:
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    event = json.loads(line)
                    run = event["session"]
                    if event["kind"] == "checkpoint":
                        raise TickFidelityError(
                            "Checkpoint lacks tick ordering; full-run rebuild required"
                        )
                    if event["kind"] == "gap" or event["gap"] or event.get("gaps"):
                        raise TickFidelityError(
                            "Recording gap: candles cannot recover tick fidelity"
                        )
                    if event["kind"] != "tick" or event["token"] != event["spot_token"]:
                        continue
                    at = local_time(timestamp(event["exchange_time"]))
                    if not any(s.opening <= at < s.closing for s in calendar.sessions):
                        raise TickFidelityError(
                            "Calendar does not establish tick session eligibility"
                        )
                    bricks.extend(renko.on_price(event["price"], at))
                    samples += 1
        if not samples:
            raise TickFidelityError("No ordered spot ticks available for restoration")
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        raise TickFidelityError(
            "Invalid or incomplete tick recording; rebuild required"
        ) from None
    return TickRestoreResult(renko, tuple(bricks), samples, run)
