"""Synthetic algorithm tests, not evidence of TradingView parity."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.market.renko_builder import RenkoBuilder
from app.tools.parity_check import main

START = datetime.fromisoformat("2026-10-23T09:15:00+05:30")


def test_seed_boundaries_reversal_and_gap() -> None:
    builder = RenkoBuilder(50, 25)
    assert builder.on_price(24030, START) == []
    up = builder.on_price(24075, START + timedelta(minutes=1))
    assert [(b.open, b.close) for b in up] == [(24025, 24075)]
    assert builder.on_price(24000, START + timedelta(minutes=2)) == []
    down = builder.on_price(23875, START + timedelta(minutes=3))
    assert [(b.open, b.close) for b in down] == [
        (24025, 23975),
        (23975, 23925),
        (23925, 23875),
    ]
    assert len({b.ts for b in down}) == 1
    assert [b.index for b in up + down] == list(range(4))


def test_first_brick_can_be_down_and_days_do_not_reset() -> None:
    builder = RenkoBuilder(50, 25)
    builder.on_price(24030, START)
    assert builder.on_price(23975, START + timedelta(days=3))[0].direction == -1


def test_duplicate_older_and_invalid_inputs_do_not_advance_state() -> None:
    builder = RenkoBuilder()
    builder.on_price(24000, START)
    assert builder.on_price(25000, START) == []
    assert builder.on_price(25000, START - timedelta(seconds=1)) == []
    with pytest.raises(ValueError):
        builder.on_price("NaN", START + timedelta(minutes=1))
    with pytest.raises(ValueError):
        builder.on_price(24050, datetime(2026, 10, 23))
    assert builder.on_price(24050, START + timedelta(minutes=1))[0].index == 0


@pytest.mark.parametrize("box,anchor", [(0, 0), (-1, 0), ("NaN", 0), (1, "Infinity")])
def test_invalid_configuration(box: str | int, anchor: str | int) -> None:
    with pytest.raises(ValueError):
        RenkoBuilder(box, anchor)


@given(st.lists(st.integers(1000, 2000), min_size=2, max_size=60))
def test_grid_size_continuation_and_two_box_reversals(prices: list[int]) -> None:
    builder = RenkoBuilder("0.5", "0.25")
    previous = None
    for index, price in enumerate(prices):
        for brick in builder.on_price(
            Decimal(price) / 10, START + timedelta(seconds=index)
        ):
            assert abs(brick.close - brick.open) == builder.box
            assert (brick.close - builder.anchor) % builder.box == 0
            if previous is not None:
                if previous.direction == brick.direction:
                    assert brick.open == previous.close
                else:
                    assert brick.open == previous.open
                    assert abs(brick.close - previous.close) == 2 * builder.box
            previous = brick


def test_csv_parity_success_mismatch_missing_and_tick_mode(tmp_path: Path) -> None:
    prices = tmp_path / "prices.csv"
    reference = tmp_path / "tv.csv"
    prices.write_text(
        "time,close\n2026-10-23T09:15:00+05:30,24000\n"
        "2026-10-23T09:16:00+05:30,24100\n",
        encoding="utf-8",
    )
    reference.write_text("Open,Close\n24000,24050\n24050,24100\n", encoding="utf-8")
    args = [
        "renko",
        "--csv",
        str(reference),
        "--prices",
        str(prices),
        "--anchor",
        "24000",
    ]
    assert main(args) == 0
    assert main(args) == 0  # Restart by replay is deterministic.
    reference.write_text("open,close\n24000,24050\n", encoding="utf-8")
    assert main(args) == 1
    prices.write_text(prices.read_text().replace("close", "price"), encoding="utf-8")
    assert main(args) == 2
    assert main(args + ["--mode", "tick"]) == 1
    reference.write_text("open,close\n", encoding="utf-8")
    assert main(args + ["--mode", "tick"]) == 2
