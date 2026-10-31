"""Independent hand-calculated sequences; synthetic tests are not TV evidence."""

import csv
import json
import re
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.indicator.engine import VARIABLES, IndicatorEngine
from app.indicator.flow import FlowBar, FuturesFlow, buildup
from app.indicator.math import (
    RMA,
    RSI,
    BarsSince,
    Series,
    Supertrend,
    crossover,
    crossunder,
    true_range,
)
from app.indicator.parity import compare
from app.indicator.settings import INPUTS, IndicatorSettings
from app.market.renko_builder import IST, Brick


def timestamp(i=0):
    return datetime(2026, 10, 28, 9, 15, tzinfo=IST) + timedelta(minutes=i)


def brick(i, opening, close):
    return Brick(
        i,
        Decimal(opening),
        Decimal(close),
        1 if close > opening else -1 if close < opening else 0,
        timestamp(i),
    )


def test_input_and_var_inventory_matches_preserved_pine():
    pine = Path("../docs/pine/renko_indicator.pine").read_text(encoding="utf-8")
    assert set(INPUTS) == set(re.findall(r"^(\w+)\s*= input\.", pine, re.M))
    names = set(
        re.findall(
            r"^var\s+(?:(?:float|int|bool|string|array<\w+>|line|label|table)\s+)?(\w+)\s*=",
            pine,
            re.M,
        )
    )
    assert set(VARIABLES) == names
    assert IndicatorSettings()["boxSize"] == 50
    assert IndicatorSettings()["atrLen"] == 10
    assert IndicatorSettings()["rsiLen"] == 14
    assert IndicatorSettings()["factor"] == 2.5


@pytest.mark.parametrize(
    "name,value",
    [
        ("atrLen", 0),
        ("rsiLen", True),
        ("boxSize", float("nan")),
        ("factor", float("inf")),
        ("orbUntil", 1160),
        ("coreWindow", 11),
        ("minGrade", "unknown"),
        ("flowOn", 1),
        ("unknown", 1),
    ],
)
def test_settings_reject_invalid(name, value):
    with pytest.raises(ValueError):
        IndicatorSettings(**{name: value})


def test_rma_seed_missing_and_recurrence():
    rma = RMA(3)
    assert [rma.update(v) for v in (None, 1, None, 2, 3, None, 6)] == [
        None,
        None,
        None,
        None,
        2,
        2,
        pytest.approx(10 / 3),
    ]
    assert rma.seed == []


@pytest.mark.parametrize("length", [0, -1, True])
def test_invalid_rma(length):
    with pytest.raises(ValueError):
        RMA(length)


@pytest.mark.parametrize(
    "values,expected",
    [
        ([1, 2, 3, 4], 100),
        ([4, 3, 2, 1], 0),
        ([2, 2, 2, 2], 100),
        ([1, 2, 1, 2], 100 * 2 / 3),
    ],
)
def test_rsi_hand_seed(values, expected):
    rsi = RSI(3)
    got = [rsi.update(v) for v in values]
    assert got[:3] == [None] * 3
    assert got[-1] == pytest.approx(expected)
    assert rsi.update(None) == pytest.approx(expected)


def test_rsi_recursion_and_missing():
    r = RSI(2)
    assert [r.update(v) for v in (10, None, 12, 11)] == [
        None,
        None,
        None,
        pytest.approx(200 / 3),
    ]
    assert r.update(13) == pytest.approx(600 / 7)


def test_true_range_and_supertrend_equal_boundaries():
    assert true_range(12, 10, None) == 2
    assert true_range(12, 10, 8) == 4
    st = Supertrend(2, 1)
    assert st.update(11, 9, 10) == (0, 1)
    assert st.update(11, 9, 10) == (12, 1)
    assert st.update(12, 10, 12) == (12, 1)  # exact upper: no flip
    assert st.update(13, 11, 13) == (10, -1)
    assert st.update(12, 10, 10) == (10, -1)  # exact lower: no flip
    # Prior close 13 -> low 10 makes TR=3; then ATR=(2.5+2)/2.
    assert st.update(10, 8, 8) == (11.25, 1)


def test_supertrend_warmup():
    st = Supertrend(3, 2)
    assert st.update(11, 9, 10) == (0, 1)
    assert st.update(12, 10, 11) == (None, 1)
    assert st.update(13, 11, 12) == (16, 1)
    assert st.atr.value == 2


def test_supertrend_recorded_reference_warmup():
    # First ten observed OHLC/ST rows, without account metadata, from export
    # SHA256 9497c1713821e75703883b5e54ffd1b451aaf53c47fbecae6f4acc5bf20f9d68.
    # Preserve zero on brick 0, missing values on 1-8, and first seeded ATR on 9.
    observed = [
        (2850, 2800, 2850, 0),
        (2900, 2850, 2900, None),
        (2942.5, 2800, 2800, None),
        (2800, 2750, 2750, None),
        (2750, 2700, 2700, None),
        (2700, 2650, 2650, None),
        (2650, 2600, 2600, None),
        (2700, 2577.25, 2700, None),
        (2750, 2700, 2750, None),
        (2800, 2750, 2800, 2941.3125),
    ]
    st = Supertrend(10, 2.5)
    for high, low, close, expected in observed:
        assert st.update(high, low, close) == (expected, 1)


def test_supertrend_length_one_preserves_band_initialization():
    st = Supertrend(1, 2)
    # With no prior band/close, Pine's nz(previous upper band) is zero.
    assert st.update(11, 9, 10) == (0, 1)
    assert st.atr.value == 2
    assert st.update(11, 9, 10) == (14, 1)


def test_helpers_na_equal_and_window_alignment():
    assert crossover(2, 1, 1, 1)
    assert not crossover(1, 1, 0, 1)
    assert not crossover(2, 1, None, 1)
    assert crossunder(0, 1, 1, 1)
    since = BarsSince()
    assert [since.update(v) for v in (False, True, False, False, True)] == [
        None,
        0,
        1,
        2,
        0,
    ]
    series = Series(4)
    for value in (1, None, 2, 3):
        series.update(value)
    assert series.sma(3) == 2
    assert series.total(3) == 6
    assert series.ago(0) == 3
    assert series.ago(4) is None
    series.update(4)
    assert series.total(3) == 9
    with pytest.raises(ValueError):
        series.ago(-1)


def test_swing_transition_and_initial_trend_age():
    e = IndicatorEngine("test", IndicatorSettings(rsiLen=1))
    assert e.process(brick(0, 100, 150))["trend_age"] == 100
    e.process(brick(1, 150, 200))
    out = e.process(brick(2, 150, 100))
    assert out["top"] == {"price": 200, "rsi": 100, "index": 1, "age": 1}
    assert out["run_length"] == 1
    out = e.process(brick(3, 150, 200))
    assert out["bottom"] == {"price": 100, "rsi": 0, "index": 2, "age": 1}


@pytest.mark.parametrize("invalid", ["duplicate", "gap", "time", "naive", "direction"])
def test_invalid_events_leave_state_unchanged(invalid):
    e = IndicatorEngine("test")
    first = brick(0, 100, 150)
    e.process(first)
    b = brick(1, 150, 200)
    b = {
        "duplicate": first,
        "gap": replace(b, index=2),
        "time": replace(b, ts=timestamp(-1)),
        "naive": replace(b, ts=datetime(2026, 10, 28)),
        "direction": replace(b, direction=-1),
    }[invalid]
    before = e.snapshot()
    with pytest.raises(ValueError):
        e.process(b)
    assert e.snapshot() == before


@pytest.mark.parametrize("split", [0, 1, 2, 10, 20])
def test_snapshot_roundtrip_matches_continuous(split):
    settings = IndicatorSettings(rsiLen=3, atrLen=3)
    bricks = [brick(i, 100 + i % 4 * 50, 150 + i % 4 * 50) for i in range(30)]
    uninterrupted = IndicatorEngine("test", settings)
    expected = [uninterrupted.process(b) for b in bricks]
    restarted = IndicatorEngine("test", settings)
    for b in bricks[:split]:
        restarted.process(b)
    restarted = IndicatorEngine.restore(
        json.loads(json.dumps(restarted.snapshot())), "test", settings
    )
    assert [restarted.process(b) for b in bricks[split:]] == expected[split:]
    assert restarted.snapshot() == uninterrupted.snapshot()


def test_snapshot_identity_and_day_reset():
    settings = IndicatorSettings(divCrossDay=False)
    e = IndicatorEngine("test", settings)
    e.process(brick(0, 100, 150))
    e.variables["lastTopP"] = 150
    e.variables["sigToday"] = 5
    e.process(replace(brick(1, 150, 200), ts=timestamp(24 * 60)))
    assert e.variables["lastTopP"] is None
    assert e.variables["sigToday"] == 0
    for stream, config in [("other", settings), ("test", IndicatorSettings())]:
        with pytest.raises(ValueError):
            IndicatorEngine.restore(e.snapshot(), stream, config)


@pytest.mark.parametrize(
    "px,oi,want",
    [
        (1, 1, 2),
        (1, -1, 1),
        (-1, 1, -2),
        (-1, -1, -1),
        (None, 1, 0),
        (1, None, 0),
        (0.01, 1, 0),
        (0.05, 0.1, 2),
    ],
)
def test_buildup_thresholds(px, oi, want):
    assert buildup(px, oi, IndicatorSettings()) == want


def flowbar(i, close=100, volume=10, oi=100):
    return FlowBar(
        timestamp(i * 5),
        timestamp((i + 1) * 5),
        close + 1,
        close - 1,
        close,
        volume,
        oi,
    )


def test_flow_previous_volume_alignment_and_missing_oi():
    flow = FuturesFlow("contract", IndicatorSettings(flowBars=1))
    for i in range(20):
        b = flowbar(i, 100 + i, 100 if i == 19 else 10, None)
        out = flow.update(b, b.end, "contract", 100, 100)
        assert out["volume_ratio"] is None
    b = flowbar(20, 120, 1, None)
    out = flow.update(b, b.end, "contract", 100, 100)
    assert out["volume_ratio"] == pytest.approx(100 / 14.5)
    assert out["window_build"] == out["day_build"] == 0
    assert out["oi_pct"] is None
    assert out["score"] == 3
    assert out["volume_spike"]


def test_flow_order_contract_completion_and_day_vwap():
    f = FuturesFlow("contract")
    b = flowbar(0)
    for at, contract in [(b.start, "contract"), (b.end, "other")]:
        with pytest.raises(ValueError):
            f.update(b, at, contract)
    f.update(b, b.end, "contract")
    with pytest.raises(ValueError):
        f.update(b, b.end, "contract")
    next_day = replace(flowbar(0, 200), start=timestamp(1440), end=timestamp(1445))
    assert f.update(next_day, next_day.end, "contract")["vwap"] == 200


def test_flow_disabled_and_oi_disabled():
    for settings in (IndicatorSettings(flowOn=False), IndicatorSettings(useOI=False)):
        f = FuturesFlow("contract", settings)
        for i in range(4):
            b = flowbar(i, 100 + i, 10, 100 + i)
            out = f.update(b, b.end, "contract", 90, 90)
        assert out["window_build"] == 0
        assert out["day_build"] == 0
        if not settings["flowOn"]:
            assert out["score"] == 0


def test_parity_hand_fixture_and_first_divergence(tmp_path):
    path = tmp_path / "debug.csv"
    fields = [
        "index",
        "time",
        "open",
        "high",
        "low",
        "close",
        "rsi",
        "supertrend",
        "direction",
    ]
    rows = [
        dict(zip(fields, [i, timestamp(i).isoformat(), o, h, low, c, r, s, d]))
        for i, (o, h, low, c, r, s, d) in enumerate(
            [
                (10, 11, 9, 10, "", 0, 1),
                (10, 11, 9, 10, 100, 12, 1),
                (10, 12, 10, 12, 100, 12, 1),
                (12, 13, 11, 13, 100, 10, -1),
            ]
        )
    ]

    def write():
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    write()
    settings = IndicatorSettings(rsiLen=1, atrLen=2, factor=1)
    assert compare(path, settings)["passed"]
    rows[1]["rsi"] = 99
    write()
    assert compare(path, settings) == {
        "passed": False,
        "index": 1,
        "column": "rsi",
        "expected": 99,
        "actual": 100,
        "tolerance": 1e-8,
    }
    with pytest.raises(ValueError):
        compare(path, settings, float("nan"))


@pytest.mark.parametrize("damage", ["index", "seed", "variables", "version", "number"])
def test_corrupt_checkpoint_rejected(damage):
    s = IndicatorSettings()
    p = IndicatorEngine("test", s).snapshot()
    if damage == "index":
        p["last_index"] = 5
    elif damage == "seed":
        p["rsi"]["gain"]["seed"] = [1] * 14
    elif damage == "variables":
        p["variables"]["runLen"] = "bad"
    elif damage == "version":
        p["version"] = 2
    else:
        p["st"]["line"] = float("nan")
    with pytest.raises(ValueError):
        IndicatorEngine.restore(p, "test", s)


def test_persistence_and_brick_context_use_isolated_database(tmp_path):
    from app.db.models import Base
    from app.db.session import database_engine
    from app.market.lifecycle_state import LifecycleStore
    from app.market.warmup import Session, SessionCalendar

    db = database_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    try:
        Base.metadata.create_all(db)
        store = LifecycleStore(db)
        settings = IndicatorSettings()
        e = IndicatorEngine("test", settings)
        b = brick(0, 100, 150)
        e.process(b)
        e.save(store)
        restored = IndicatorEngine.restore(
            store.read("indicator:test"), "test", settings
        )
        assert restored.snapshot() == e.snapshot()
        calendar = SessionCalendar(
            timestamp().date(),
            timestamp().date(),
            (Session(timestamp(), timestamp(375)),),
        )
        context = e.context(store, 111, calendar, b)
        assert context["open"] is None
        assert context["previous_close"] is None
        assert context["opening_range"]["state"] == "forming"
        assert not context["entries_enabled"]
    finally:
        db.dispose()


def test_exchange_aligned_flow_and_gap_rejection():
    from app.market.warmup import Session, SessionCalendar

    calendar = SessionCalendar(
        timestamp().date(), timestamp().date(), (Session(timestamp(), timestamp(375)),)
    )
    flow = FuturesFlow("contract", calendar=calendar)
    bar = flowbar(0)
    with pytest.raises(ValueError, match="aligned"):
        flow.update(replace(bar, end=timestamp(4)), timestamp(5), "contract")
    flow.update(bar, bar.end, "contract")
    later = flowbar(2)
    with pytest.raises(ValueError, match="missing"):
        flow.update(later, later.end, "contract")


def test_cross_day_swing_resets_before_transition_and_equal_time_order():
    e = IndicatorEngine("test", IndicatorSettings(divCrossDay=False, rsiLen=1))
    e.process(brick(0, 100, 150))
    # Pine resets previous swing, then captures yesterday's final green brick.
    out = e.process(replace(brick(1, 150, 100), ts=timestamp(1440)))
    assert out["top"]["index"] == 0
    assert out["top"]["price"] == 150
    assert e.process(replace(brick(2, 100, 150), ts=timestamp(1440)))["index"] == 2
