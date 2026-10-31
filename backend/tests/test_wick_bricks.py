"""Observed wick transport, legacy identity and immutable input validation."""

import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.live_contracts import BrickData
from app.market.persistence import brick_from, encode
from app.market.renko_builder import Brick, WickBrick

AT = datetime.fromisoformat("2026-10-27T13:25:00+05:30")


def observed(**changes):
    fields = dict(
        index=0,
        open=Decimal(22750),
        close=Decimal(22700),
        direction=-1,
        ts=AT,
        wick_high=Decimal("22804.85"),
        wick_low=Decimal(22700),
    )
    return WickBrick(**(fields | changes))


def test_observed_wick_survives_storage_and_wire_without_rounding():
    brick = observed()
    restored = brick_from(json.loads(encode(asdict(brick))))
    assert restored == brick
    assert restored.high == Decimal("22804.85")
    assert restored.low == Decimal(22700)
    wire = BrickData.model_validate(asdict(restored)).model_dump(mode="json")
    assert wire["wick_high"] == "22804.85"
    assert wire["wick_low"] == "22700"


def test_legacy_body_payload_identity_is_unchanged():
    brick = Brick(0, Decimal(22750), Decimal(22700), -1, AT)
    payload = asdict(brick)
    assert set(payload) == {"index", "open", "close", "direction", "ts", "volume"}
    assert type(brick_from(json.loads(encode(payload)))) is Brick
    assert brick_from(json.loads(encode(payload))) == brick
    assert BrickData.model_validate(payload).wick_high is None


@pytest.mark.parametrize(
    "changes",
    [
        {"wick_high": Decimal(22749)},
        {"wick_low": Decimal(22701)},
        {"wick_low": Decimal(0)},
        {"wick_high": Decimal("NaN")},
        {"wick_high": Decimal("Infinity")},
    ],
)
def test_invalid_wicks_are_rejected_before_storage(changes):
    with pytest.raises(ValueError, match="wick"):
        observed(**changes)


def test_api_and_restore_reject_incomplete_or_inverted_wicks():
    data = asdict(observed())
    for changed in (data | {"wick_low": None}, data | {"wick_high": "22749"}):
        with pytest.raises(ValidationError):
            BrickData.model_validate(changed)
        with pytest.raises(ValueError):
            brick_from(json.loads(encode(changed)))


def test_changed_wick_is_part_of_durable_identity():
    before = observed()
    after = observed(wick_high=Decimal("22805.85"))
    assert before.open == after.open and before.close == after.close
    assert encode(asdict(before)) != encode(asdict(after))
