"""Read-only comparison of recorded chart settings with managed Renko support.

Never imports app.main, opens a database, logs into Kite or changes settings.
Compatibility is a prerequisite for isolated validation, not paper admission.
"""

import argparse
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import AwareDatetime, BaseModel, Field, JsonValue, StrictBool

from app.config import BACKEND_DIR, Settings

DEFAULT_REFERENCE = BACKEND_DIR.parent / "docs/pine/reference_package.actual.json"


class ChartReference(BaseModel):
    exchange_symbol: str | None = None
    resolution: str | None = None
    renko_method: str | None = None
    box_size: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    price_source: str | None = None
    wicks_enabled: StrictBool | None = None
    timezone: str | None = None
    anchor_completed_brick_close: Decimal | None = Field(
        default=None, gt=0, allow_inf_nan=False
    )
    anchor_timestamp: AwareDatetime | None = None
    loaded_history_start: AwareDatetime | None = None
    reference_start: AwareDatetime | None = None
    reference_end: AwareDatetime | None = None


class ReferencePackage(BaseModel):
    chart: ChartReference = Field(default_factory=ChartReference)
    indicator_input_overrides: dict[str, JsonValue] | None = None


def compare(settings: Settings, package: dict[str, Any]) -> dict[str, Any]:
    reference = ReferencePackage.model_validate(package)
    chart = reference.chart
    blockers: list[dict[str, str]] = []

    def block(code: str, reason: str) -> None:
        blockers.append({"code": code, "reason": reason})

    for name in ChartReference.model_fields:
        if getattr(chart, name) is None:
            block(f"missing_{name}", f"Actual chart evidence missing: {name}")
    if chart.renko_method not in (None, "Traditional"):
        block("method_unsupported", "Managed builder supports Traditional Renko only")
    if chart.price_source not in (None, "Close"):
        block("source_unsupported", "Managed builder supports Close source only")
    if chart.exchange_symbol not in (None, "NSE:NIFTY"):
        block("symbol_unsupported", "Managed source is NSE NIFTY 50")
    if chart.timezone not in (None, "Asia/Kolkata"):
        block("timezone_mismatch", "Managed session alignment uses Asia/Kolkata")
    if chart.resolution not in (None, "1"):
        block(
            "interval_unsupported",
            "Managed Renko consumes minute closes; reference interval is "
            f"{chart.resolution} minutes. Futures flow timeframe is independent.",
        )
    if chart.wicks_enabled:
        block(
            "wicks_unsupported",
            "Managed Brick high/low are body-only; full parity rejects wick OHLC. "
            "Preserve actual wick data; do not remove it to force a match.",
        )
    if settings.renko_mode != "minute_close":
        block("runtime_mode_unsupported", "Managed pipeline requires minute_close")
    if (
        chart.box_size is not None
        and Decimal(str(settings.renko_box)) != chart.box_size
    ):
        block("box_mismatch", "Configured box differs from the actual chart")
    if settings.renko_anchor is None:
        block("runtime_anchor_missing", "Reference anchor recorded but not configured")
    elif chart.anchor_completed_brick_close is not None and chart.box_size is not None:
        # Any anchor on the same box grid is equivalent; timestamps remain lineage.
        difference = (
            Decimal(str(settings.renko_anchor)) - chart.anchor_completed_brick_close
        )
        if difference % chart.box_size:
            block("anchor_grid_mismatch", "Configured anchor lies on a different grid")
    if reference.indicator_input_overrides is None:
        block("inputs_unconfirmed", "Only some saved indicator inputs are observed")
    if chart.reference_start and chart.reference_end:
        if chart.reference_start > chart.reference_end:
            block("reference_range_invalid", "Reference start is after reference end")
    return {
        "status": "BLOCKED" if blockers else "READY_FOR_ISOLATED_VALIDATION",
        "paper_trading_ready": False,
        "genuine_feed_verified": False,
        "reference_parity_verified": False,
        "chart": chart.model_dump(mode="json"),
        "configured": {
            "box": settings.renko_box,
            "anchor": settings.renko_anchor,
            "mode": settings.renko_mode,
        },
        "managed_capabilities": {"source_minutes": 1, "wicks": False},
        "blockers": blockers,
        "operator_state_changed": False,
        "note": (
            "A recorded grid anchor is not a historical seed or a matching sequence."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--check", action="store_true", help="Exit 2 when blocked")
    args = parser.parse_args()
    package = json.loads(args.reference.read_text(encoding="utf-8"))
    report = compare(Settings(), package)
    report["checked_at"] = datetime.now().astimezone().isoformat()
    print(json.dumps(report, indent=2))
    if args.check and report["status"] == "BLOCKED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
