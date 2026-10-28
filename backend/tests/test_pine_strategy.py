"""Pine rule regressions; all observations here are synthetic development inputs."""

import copy
import json
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.db.models import Base, IndicatorCheckpoint, IndicatorEvent, IndicatorResult
from app.db.session import database_engine
from app.indicator.engine import IndicatorEngine
from app.indicator.features import divergence, outlook_bias
from app.indicator.persistence import IndicatorRepository
from app.indicator.settings import IndicatorSettings
from app.indicator.signals import (
    PRIORITY,
    TYPES,
    grade,
    raw_signals,
    risk,
    select_signals,
)
from app.indicator.strategy import PineContext, PineEngine
from app.indicator.text import HELPERS, parse
from app.indicator.trades import explanation, signal_statistics, trade_id, trade_step
from app.market.renko_builder import IST, Brick


def settings(**kw):
    return IndicatorSettings(**({"minGrade": "Weak and above (all)"} | kw))


def state():
    return IndicatorEngine("test").variables


def at(minute=0):
    return datetime(2026, 10, 28, 10, tzinfo=IST) + timedelta(minutes=minute)


def brick(i, opening, close):
    return Brick(
        i,
        Decimal(opening),
        Decimal(close),
        1 if close > opening else -1 if close < opening else 0,
        at(i),
    )


def features(**kw):
    return (
        dict(
            index=10,
            close=150,
            open=100,
            high=150,
            low=100,
            rsi=60,
            previous_rsi=55,
            brick_direction=1,
            is_up=True,
            flipped=False,
            bars_since_flip=1,
            trend_age=2,
            minute=600,
            bull_div=False,
            bear_div=False,
            hidden_bull=False,
            hidden_bear=False,
            bull_forming=False,
            bear_forming=False,
            flow_ok=False,
            flow_score=0,
            vwap_side=0,
            volume_side=0,
            late_long=False,
            late_short=False,
            bias_score=6,
            bias_direction=1,
            stretched=False,
            support=None,
            resistance=None,
            choppy=False,
            supertrend=50,
            run_length=2,
            previous_high=None,
            previous_low=None,
            day_high=None,
            day_low=None,
            day_open=None,
            previous_close=None,
            time_ms=int(at().timestamp() * 1000),
            divergence_text="",
        )
        | kw
    )


@pytest.mark.parametrize("sd", [1, -1])
@pytest.mark.parametrize("typ", TYPES)
def test_each_signal_raw_condition(typ, sd):
    v = state()
    f = features(
        brick_direction=sd,
        is_up=sd == 1,
        close=150 if sd == 1 else 50,
        bull_div=typ == "DIV" and sd == 1,
        bear_div=typ == "DIV" and sd == -1,
        hidden_bull=typ == "HDIV" and sd == 1,
        hidden_bear=typ == "HDIV" and sd == -1,
    )
    previous = {
        "brick_direction": -sd,
        "close": 100,
        "last_top": 120,
        "last_bottom": 80,
    }
    v.update(lastTopP=120, lastTopI=9, lastBotP=80, lastBotI=9)
    if typ == "ORB":
        v.update(orH=120 if sd == 1 else 180, orL=20 if sd == 1 else 80)
    if typ == "TRAP":
        v["trapDnBar" if sd == 1 else "trapUpBar"] = 9
        v["trapDnLvl" if sd == 1 else "trapUpLvl"] = 100
    if typ == "SRG":
        f.update(flow_ok=True, flow_score=4 * sd, volume_side=sd)
    if typ == "PB":
        f["trend_age"] = 3
    raw = raw_signals(v, previous, f, settings())
    assert raw[sd][typ]


def test_core_window_once_flip_and_rejected_grade_does_not_consume():
    v = state()
    f = features(bars_since_flip=3)
    assert not raw_signals(v, {}, f, settings())[1]["CORE"]
    f["bars_since_flip"] = 2
    assert raw_signals(v, {}, f, settings())[1]["CORE"]
    v["coreDone"] = True
    assert not raw_signals(v, {}, f, settings())[1]["CORE"]
    f["flipped"] = True
    assert raw_signals(v, {}, f, settings())[1]["CORE"]


@pytest.mark.parametrize("sd", [1, -1])
def test_priority_cooldown_exemptions_and_no_grade_fallback(sd):
    v = state()
    f = features(bias_score=-10 * sd, index=10)
    v["lastSigL" if sd == 1 else "lastSigS"] = 9
    raw = {d: {name: d == sd for name in PRIORITY} for d in (1, -1)}
    candidates = select_signals(raw, v, f, settings())
    assert next(x for x in candidates if x["accepted"])["type"] == "DIV"
    assert next(x for x in candidates if x["type"] == "PB")["reason"] == "cooldown"
    raw[sd]["DIV"] = False
    assert (
        next(x for x in select_signals(raw, v, f, settings()) if x["accepted"])["type"]
        == "CORE"
    )
    # A selected low-grade CORE blocks a higher-grade lower-priority TRAP.
    v["lastSigL" if sd == 1 else "lastSigS"] = -999
    f.update(
        flow_ok=True,
        flow_score=sd,
        vwap_side=sd,
        support=150,
        resistance=150,
        stretched=True,
    )
    got = select_signals(raw, v, f, settings(minGrade="Strong only"))
    assert not any(x["accepted"] for x in got)
    assert (
        next(x for x in got if x["type"] == "CORE")["reason"] == "below_minimum_grade"
    )


@pytest.mark.parametrize("gap,expected", [(59, True), (60, True), (61, False)])
@pytest.mark.parametrize("sd", [1, -1])
def test_regular_divergence_gap_and_half_box_threshold(gap, expected, sd):
    v = state()
    side = "Bot" if sd == 1 else "Top"
    v.update({f"last{side}P": 100, f"last{side}R": 50, f"last{side}I": 0})
    old = copy.deepcopy(v)
    prev = {"brick_direction": -sd, "close": 100, "rsi": 50 + sd}
    f = features(index=gap + 1, brick_direction=sd, is_up=sd == 1)
    divergence(v, old, prev, f, settings())
    assert f["bull_div" if sd == 1 else "bear_div"] == expected


@pytest.mark.parametrize(
    "mode,price,expected",
    [
        ("Equal only", 125, False),
        ("Equal only", 124.99, True),
        ("Equal or higher", 125, True),
    ],
)
def test_divergence_price_modes(mode, price, expected):
    v = state()
    v.update(lastTopP=100, lastTopR=70, lastTopI=1)
    f = features(index=10, brick_direction=-1)
    divergence(
        v,
        copy.deepcopy(v),
        {"brick_direction": 1, "close": price, "rsi": 65},
        f,
        settings(topType=mode),
    )
    assert f["bear_div"] == expected


@pytest.mark.parametrize("sd", [1, -1])
def test_hidden_and_forming_divergence(sd):
    v = state()
    side = "Bot" if sd == 1 else "Top"
    v.update({f"last{side}P": 100, f"last{side}R": 50, f"last{side}I": 1})
    f = features(brick_direction=sd, is_up=sd == 1)
    divergence(
        v,
        copy.deepcopy(v),
        {"brick_direction": -sd, "close": 100 + 50 * sd, "rsi": 50 - sd},
        f,
        settings(),
    )
    assert f["hidden_bull" if sd == 1 else "hidden_bear"]
    f = features(brick_direction=-sd, close=100, rsi=50 + sd, is_up=sd == 1)
    divergence(v, copy.deepcopy(v), {}, f, settings())
    assert f["bull_forming" if sd == 1 else "bear_forming"]


def test_orb_consumed_even_when_disabled_and_cutoff_is_exclusive():
    v = state()
    v.update(orH=120, orL=20)
    f = features()
    assert not raw_signals(v, {}, f, settings(orbOn=False))[1]["ORB"]
    assert v["orbUpSeen"]
    assert not raw_signals(v, {}, f, settings())[1]["ORB"]
    v["orbUpSeen"] = False
    f["minute"] = 690
    assert not raw_signals(v, {}, f, settings())[1]["ORB"]


def test_trap_inclusive_window_and_expiration_and_no_same_bar_failure():
    for age, want in [(0, False), (6, True), (7, False)]:
        v = state()
        v.update(trapDnBar=10 - age, trapDnLvl=100)
        assert raw_signals(v, {}, features(), settings())[1]["TRAP"] == want


def test_surge_onset_two_bricks_and_rearm_requires_new_onset():
    v = state()
    s = settings()
    f = features(flow_ok=True, flow_score=4, volume_side=1)
    assert raw_signals(v, {}, f, s)[1]["SRG"]
    for age, want in [(2, True), (3, False)]:
        f["index"] = 10 + age
        assert raw_signals(v, {"surge_L": True}, f, s)[1]["SRG"] == want
    f["index"] = 20
    assert raw_signals(v, {"surge_L": False}, f, s)[1]["SRG"]


@pytest.mark.parametrize(
    "score,late,want",
    [(5, False, 3), (4, False, 2), (2, False, 2), (1, False, 1), (5, True, 2)],
)
def test_alignment_grades(score, late, want):
    assert (
        grade("CORE", 1, features(bias_score=score, late_long=late), settings()) == want
    )


def test_reversal_evidence_grade_and_risk():
    f = features(flow_ok=True, flow_score=1, vwap_side=1)
    assert grade("DIV", 1, f, settings()) == 3  # flow, VWAP and rising RSI
    assert risk("DIV", 1, f, settings())["count"] == 1
    assert grade("DIV", 1, features(rsi=50), settings()) == 1


@pytest.mark.parametrize(
    "start,score,want",
    [(0, 4, 1), (0, -4, -1), (1, 2, 1), (1, 1, 0), (-1, -2, -1), (-1, -1, 0)],
)
def test_bias_hysteresis(start, score, want):
    # Choose Supertrend/run/RSI/day/flow factors to produce independently known scores.
    v = state()
    v["biasDir"] = start
    f = features(
        is_up=score > 0,
        brick_direction=1 if score > 0 else -1,
        run_length=1,
        rsi=50,
        flow_ok=True,
        flow_score=0,
    )
    base = 2 if score > 0 else -2
    remainder = score - base
    if abs(remainder) == 2:
        f["flow_score"] = 3 if remainder > 0 else -3
    elif abs(remainder) == 1:
        f["flow_score"] = 1 if remainder > 0 else -1
    outlook_bias(v, {}, f, settings(), [])
    assert f["bias_score"] == score
    assert f["bias_direction"] == want


def test_outlook_buckets_samples_and_support_nearest():
    v = state()
    v["nTot"][1] = 5
    v["nCont"][1] = 3
    f = features(run_length=2, day_high=200, previous_high=175, day_low=100)
    outlook_bias(v, {}, f, settings(outSamples=5), [])
    assert f["continuation_probability"] == 60
    assert f["resistance"] == 175 and f["support"] == 100


def signal(typ="CORE", sd=1):
    return {
        "type": typ,
        "direction": sd,
        "grade": 3,
        "accepted": True,
        "risk": {"label": "Low", "count": 0, "text": "nothing unusual."},
        "explanation": {"tooltip": "signal"},
    }


def test_trade_id_exact_vectors():
    assert trade_id(0, 0) == "[AAAAA]"
    assert trade_id(0, 1) == "[AAAAB]"
    assert trade_id(0, 39) == "[AAAA!]"
    assert trade_id(0, 40) == "[AAABA]"
    assert len(trade_id(1, 0)) == 7


def test_trade_entry_no_same_brick_exit_same_direction_ignore_targets_and_exit():
    v = state()
    f = features(index=1, close=1000, supertrend=900)
    s = settings()
    assert [e["kind"] for e in trade_step(v, f, s, [signal()])] == ["ENTRY"]
    tid = v["posId"]
    assert v["posT1"] == 1025 and v["posT2"] == 1040
    assert trade_step(v, f, s, [signal()]) == []
    f.update(index=2, close=1030)
    assert [e["kind"] for e in trade_step(v, f, s, [])] == ["T1"]
    f.update(index=3, close=1040)
    events = trade_step(v, f, s, [])
    assert [e["kind"] for e in events] == ["EXIT"]
    assert events[0]["trade_id"] == tid and events[0]["target_2_hit"]
    assert v["cN"][0] == v["cW"][0] == v["cT1"][0] == v["cT2"][0] == 1


def test_exit_before_reentry_and_t1_suppression_on_exit():
    v = state()
    s = settings()
    f = features(index=1, close=1000, supertrend=900)
    trade_step(v, f, s, [signal()])
    old = v["posId"]
    f.update(index=2, close=1030, brick_direction=-1)
    events = trade_step(v, f, s, [signal("PB", -1)])
    assert [e["kind"] for e in events] == ["EXIT", "ENTRY"]
    assert events[0]["trade_id"] == old and events[1]["trade_id"] != old
    assert events[0]["target_1_hit"]


def test_nondefault_opposite_signal_replacement_is_not_fabricated_exit():
    v = state()
    s = settings(exitOppN=2)
    f = features(index=1, close=1000, supertrend=900)
    trade_step(v, f, s, [signal()])
    old = v["posId"]
    f.update(index=2, close=950, brick_direction=-1)
    out = trade_step(v, f, s, [signal("DIV", -1)])
    assert [e["kind"] for e in out] == ["ENTRY"]
    assert out[0]["replaced_trade_id"] == old
    assert v["trN"] == 0


def test_safety_stop_after_target_one_and_target_two_exit_priority():
    v = state()
    s = settings(exitOnStop=True)
    f = features(index=1, close=1000, supertrend=900)
    trade_step(v, f, s, [signal()])
    f.update(index=2, close=1030)
    trade_step(v, f, s, [])
    assert v["posStop"] == 1000
    f.update(index=3, close=1000)
    assert trade_step(v, f, s, [])[0]["reason"] == "safety"


def test_pending_signal_statistics_inclusive_age_and_zero_is_not_win():
    v = state()
    s = settings(evalBricks=2)
    f = features(index=1, close=1000)
    signal_statistics(v, f, s, [signal()])
    signal_statistics(v, f | {"index": 2}, s, [])
    assert v["tN"][0] == 0
    signal_statistics(v, f | {"index": 3}, s, [])
    assert v["tN"][0] == 1 and v["tW"][0] == 0 and not v["pBar"]


@pytest.mark.parametrize("typ", TYPES)
@pytest.mark.parametrize("sd", [1, -1])
def test_explanation_helpers_and_exact_source_resource(typ, sd):
    v = state()
    f = features()
    sig = signal(typ, sd)
    explanation_data = explanation(sig, v, f, settings())
    assert "Why now:" in explanation_data["tooltip"]
    assert explanation_data["name"]
    for helper in HELPERS.values():
        parse(helper["expression"])
    pine = Path("../docs/pine/renko_indicator.pine").read_text(encoding="utf-8")
    assert all(helper["expression"] in pine for helper in HELPERS.values())


@pytest.mark.parametrize("split", [0, 1, 3, 10, 31, 60])
def test_restart_matches_uninterrupted_signal_trade_statistics_and_id(split):
    s = settings(atrLen=2, rsiLen=2, evalBricks=2)
    prices = [1000, 1050, 1100, 1150, 1100, 1050, 1000, 950] * 10
    bricks = [brick(i, prices[i], prices[i + 1]) for i in range(len(prices) - 1)]
    continuous = PineEngine("test", s)
    expected = [continuous.process(b) for b in bricks]
    restarted = PineEngine("test", s)
    for b in bricks[:split]:
        restarted.process(b)
    restarted = PineEngine.restore(
        json.loads(json.dumps(restarted.snapshot())), "test", s
    )
    assert [restarted.process(b) for b in bricks[split:]] == expected[split:]
    assert restarted.snapshot() == continuous.snapshot()
    assert any(r["events"] for r in expected)


def test_invalid_or_future_context_does_not_mutate_state():
    e = PineEngine("test")
    before = e.snapshot()
    b = brick(0, 100, 150)
    for ctx in [
        PineContext(available_at=at(1)),
        PineContext(day_open=100),
        PineContext(flow_score=6),
        PineContext(day_high=float("nan")),
    ]:
        with pytest.raises(ValueError):
            e.process(b, ctx)
        assert e.snapshot() == before


def test_engine_cross_day_reset_and_missing_context():
    e = PineEngine("test", settings(divCrossDay=False))
    r = e.process(brick(0, 100, 150))
    assert r["factors"]["day"] == r["factors"]["flow"] == 0
    e.base.variables.update(orH=500, orL=100, orbUpSeen=True, sigToday=5, trapUpBar=0)
    e.process(replace(brick(1, 150, 200), ts=at(1440)))
    v = e.base.variables
    assert v["orH"] is None and v["trapUpBar"] is None and v["sigToday"] == 0


@pytest.fixture
def db(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'indicator.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_atomic_repository_retry_changed_identity_and_restart(db):
    s = settings(atrLen=2, rsiLen=2)
    repository = IndicatorRepository(db, "test", s)
    prices = [1000, 1050, 1100, 1150, 1100, 1050, 1000, 1050]
    continuous = PineEngine("test", s)
    for i in range(len(prices) - 1):
        b = brick(i, prices[i], prices[i + 1])
        expected = continuous.process(b)
        assert repository.process(b) == expected
        assert IndicatorRepository(db, "test", s).process(b) == expected
    with Session(db) as session:
        assert session.get(IndicatorCheckpoint, "test").index == len(prices) - 2
        assert len(session.scalars(select(IndicatorResult)).all()) == len(prices) - 1
        assert session.scalars(select(IndicatorEvent)).all()
    with pytest.raises(ValueError, match="identity"):
        repository.process(replace(b, volume=Decimal(99)))


def test_database_failure_rolls_back_checkpoint_result_events(db):
    repo = IndicatorRepository(db, "test", settings(atrLen=2, rsiLen=2))

    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("INSERT INTO indicator_results"):
            raise RuntimeError("injected write failure")

    event.listen(db, "before_cursor_execute", fail)
    with pytest.raises(RuntimeError, match="injected"):
        repo.process(brick(0, 100, 150))
    event.remove(db, "before_cursor_execute", fail)
    with Session(db) as session:
        assert session.get(IndicatorCheckpoint, "test") is None
        assert not session.scalars(select(IndicatorResult)).all()
        assert not session.scalars(select(IndicatorEvent)).all()
    assert repo.process(brick(0, 100, 150))["index"] == 0


def test_existing_checkpoint_write_failure_preserves_previous_committed_state(db):
    repo = IndicatorRepository(db, "test", settings())
    repo.process(brick(0, 100, 150))
    with Session(db) as session:
        before = session.get(IndicatorCheckpoint, "test").payload

    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("INSERT INTO indicator_results"):
            raise RuntimeError("second write failure")

    event.listen(db, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError):
            repo.process(brick(1, 150, 200))
    finally:
        event.remove(db, "before_cursor_execute", fail)
    with Session(db) as session:
        assert session.get(IndicatorCheckpoint, "test").payload == before
        assert session.get(IndicatorResult, ("test", 1)) is None
    assert repo.process(brick(1, 150, 200))["index"] == 1


def test_concurrent_stale_writer_cannot_commit_twice(db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.exc import SQLAlchemyError

    s = settings()
    repo = IndicatorRepository(db, "test", s)
    repo.process(brick(0, 100, 150))
    barrier = Barrier(2)
    original = PineEngine.process

    def synchronized(self, b, context=None):
        barrier.wait(timeout=10)
        return original(self, b, context)

    monkeypatch.setattr(PineEngine, "process", synchronized)

    def attempt():
        try:
            return IndicatorRepository(db, "test", s).process(brick(1, 150, 200))
        except (RuntimeError, SQLAlchemyError) as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(isinstance(r, dict) for r in results) == 1
    with Session(db) as session:
        assert session.get(IndicatorCheckpoint, "test").index == 1
        assert len(session.scalars(select(IndicatorResult)).all()) == 2


@pytest.mark.parametrize("sd", [1, -1])
def test_trade_direction_targets_stop_cap_and_family_statistics(sd):
    v = state()
    s = settings()
    f = features(index=1, close=1000, supertrend=1000 - sd * 500, is_up=sd == 1)
    entry = trade_step(v, f, s, [signal("HDIV", sd)])[0]
    assert entry["target_1"] == 1000 * (1 + sd * 0.025)
    assert entry["target_2"] == 1000 * (1 + sd * 0.04)
    assert entry["stop"] == 1000 - sd * 300
    f.update(index=2, close=1000 + sd * 50)
    out = trade_step(v, f, s, [])
    assert [e["kind"] for e in out] == ["EXIT"]
    assert v["cN"][2 + (0 if sd == 1 else 1)] == 1
    assert out[0]["percent"] == 5


def test_flow_disabled_input_overrides_provided_context():
    engine = PineEngine("test", settings(flowOn=False))
    context = PineContext(
        available_at=at(), flow_ok=True, flow_score=5, vwap_side=1, volume_side=1
    )
    result = engine.process(brick(0, 100, 150), context)
    assert (
        not result["flow_ok"]
        and result["flow_score"] == 0
        and result["factors"]["flow"] == 0
    )


def test_late_entry_looks_at_twelve_bricks_only_after_index_twelve():
    engine = PineEngine("test", settings(atrLen=2, rsiLen=2))
    for i in range(14):
        result = engine.process(brick(i, 1000 + i * 50, 1050 + i * 50))
        assert result["late_long"] == (i > 12)
