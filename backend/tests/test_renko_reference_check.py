"""Reference diagnostics must never turn settings evidence into readiness."""

import copy
import json
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, Settings
from app.market.renko_builder import Brick
from app.tools.renko_reference_check import DEFAULT_REFERENCE, compare


def complete_package():
    return {
        "chart": {
            "exchange_symbol": "NSE:NIFTY",
            "resolution": "1",
            "renko_method": "Traditional",
            "box_size": "50",
            "price_source": "Close",
            "wicks_enabled": False,
            "timezone": "Asia/Kolkata",
            "anchor_completed_brick_close": "22700",
            "anchor_timestamp": "2026-10-27T13:25:00+05:30",
            "loaded_history_start": "2026-10-01T09:15:00+05:30",
            "reference_start": "2026-10-01T09:15:00+05:30",
            "reference_end": "2026-10-27T15:30:00+05:30",
        },
        "indicator_input_overrides": {},
    }


def codes(report):
    return {b["code"] for b in report["blockers"]}


def test_actual_screenshots_resolve_anchor_but_not_construction():
    package = json.loads(DEFAULT_REFERENCE.read_text(encoding="utf-8"))
    before = copy.deepcopy(package)
    settings = Settings(_env_file=None, renko_anchor=22700)
    report = compare(settings, package)
    assert {"interval_unsupported", "wicks_unsupported"} <= codes(report)
    assert "missing_anchor_timestamp" not in codes(report)
    assert "missing_price_source" not in codes(report)
    assert "missing_wicks_enabled" not in codes(report)
    assert "inputs_unconfirmed" in codes(report)
    assert report["status"] == "BLOCKED"
    assert not report["paper_trading_ready"]
    assert package == before and settings.renko_anchor == 22700


@pytest.mark.parametrize("anchor", [22700, 0, 22750])
def test_equivalent_grid_never_claims_feed_or_parity_acceptance(anchor):
    report = compare(Settings(_env_file=None, renko_anchor=anchor), complete_package())
    assert report["status"] == "READY_FOR_ISOLATED_VALIDATION"
    assert not report["paper_trading_ready"]
    assert not report["genuine_feed_verified"]
    assert not report["reference_parity_verified"]
    assert not report["operator_state_changed"]


def test_missing_anchor_and_wrong_grid_are_distinct():
    assert "runtime_anchor_missing" in codes(
        compare(Settings(_env_file=None), complete_package())
    )
    assert "anchor_grid_mismatch" in codes(
        compare(Settings(_env_file=None, renko_anchor=22701), complete_package())
    )


def test_five_minute_profile_resolves_capability_only_not_readiness():
    package = complete_package()
    package["chart"].update(resolution="5", wicks_enabled=True)
    report = compare(
        Settings(_env_file=None, renko_anchor=22700, renko_source_minutes=5), package
    )
    assert report["status"] == "READY_FOR_ISOLATED_VALIDATION"
    assert not {"interval_unsupported", "wicks_unsupported"} & codes(report)
    assert not report["paper_trading_ready"] and not report["genuine_feed_verified"]
    package["chart"]["wicks_enabled"] = False
    mismatch = compare(
        Settings(_env_file=None, renko_anchor=22700, renko_source_minutes=5), package
    )
    assert "wicks_mismatch" in codes(mismatch)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "0", "-1"])
def test_invalid_box_fails_before_any_configuration_change(value):
    package = complete_package()
    package["chart"]["box_size"] = value
    with pytest.raises(ValidationError):
        compare(Settings(_env_file=None), package)


def test_unknown_and_naive_reference_timestamp_cannot_be_accepted():
    package = complete_package()
    package["chart"]["anchor_timestamp"] = None
    assert "missing_anchor_timestamp" in codes(
        compare(Settings(_env_file=None, renko_anchor=22700), package)
    )
    package["chart"]["anchor_timestamp"] = "2026-10-27T13:25:00"
    with pytest.raises(ValidationError):
        compare(Settings(_env_file=None), package)


def test_capability_report_matches_current_brick_and_preserved_pine():
    brick = Brick(
        0,
        Decimal(22750),
        Decimal(22700),
        -1,
        datetime.fromisoformat("2026-10-27T13:25:00+05:30"),
    )
    assert brick.high == 22750 and brick.low == 22700
    # The screenshot's high=22804.85 cannot be represented by this body-only type.
    assert brick.high != Decimal("22804.85")
    original = BACKEND_DIR.parent / "docs/pine/renko_indicator.pine"
    assert original.is_file()


@pytest.mark.parametrize("overrides", [False, [], "defaults"])
def test_malformed_input_confirmation_does_not_clear_blocker(overrides):
    package = complete_package()
    package["indicator_input_overrides"] = overrides
    with pytest.raises(ValidationError):
        compare(Settings(_env_file=None), package)
