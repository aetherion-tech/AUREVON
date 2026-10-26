"""Explicit tick restoration never uses broker data or a minute checkpoint."""

import json
from datetime import timedelta

import pytest
from test_tick_recording import START, tick

from app.broker.kite_ticker import TickerWorker
from app.market.persistence import builder_state, encode
from app.market.renko_builder import RenkoBuilder
from app.market.tick_recording import TickRecorder
from app.market.tick_restore import TickFidelityError, restore_tick_renko
from app.market.warmup import Session, SessionCalendar

CALENDAR = SessionCalendar(
    START.date(), START.date(), (Session(START, START + timedelta(minutes=375)),)
)


def record(tmp_path, prices=(100, 130, 110, 140)):
    recorder = TickRecorder(tmp_path, 111, 222)
    worker = TickerWorker(None, 111, 222, recorder=recorder)
    for price in prices:
        worker._accept(tick(111, START, price, 100), START)
    return recorder, sorted(recorder.directory.glob("*.jsonl"))


def restore(paths, **kwargs):
    return restore_tick_renko(paths, box=10, anchor=100, calendar=CALENDAR, **kwargs)


def test_complete_order_restores_equal_time_updates_and_repeats(tmp_path):
    recorder, paths = record(tmp_path)
    before = [p.read_bytes() for p in paths]
    actual = restore(paths, ordering_complete=True)
    expected = RenkoBuilder(10, 100, mode="tick")
    bricks = []
    for price in (100, 130, 110, 140):
        bricks.extend(expected.on_price(price, START))
    assert actual.bricks == tuple(bricks)
    assert len(actual.bricks) == 6
    assert actual.samples == 4
    assert actual.source_run == recorder.directory.name
    assert actual.fidelity == "recorded_order_only"
    assert actual.entries_enabled is False
    assert restore(paths, ordering_complete=True).bricks == actual.bricks
    assert before == [p.read_bytes() for p in paths]


def test_equal_time_order_is_material_not_sorted_by_price(tmp_path):
    _, first = record(tmp_path / "a", (100, 130, 110))
    _, second = record(tmp_path / "b", (100, 110, 130))
    assert (
        restore(first, ordering_complete=True).bricks
        != restore(second, ordering_complete=True).bricks
    )
    assert RenkoBuilder(10, 100).on_price(100, START) == []
    minute = RenkoBuilder(10, 100)
    minute.on_price(100, START)
    assert minute.on_price(130, START) == []


@pytest.mark.parametrize(
    "damage",
    [
        "no_attestation",
        "gap",
        "sequence",
        "truncated",
        "seed",
        "no_spot",
        "wrong_calendar",
    ],
)
def test_unavailable_tick_fidelity_is_explicit(tmp_path, damage):
    recorder, paths = record(tmp_path)
    if damage == "gap":
        recorder.write("gap", START, {"gap": True, "gaps": []})
    elif damage in ("sequence", "truncated"):
        if damage == "truncated":
            paths[0].write_text(paths[0].read_text() + "{")
        else:
            rows = [json.loads(x) for x in paths[0].read_text().splitlines()]
            rows[1]["sequence"] = 8
            paths[0].write_text("".join(json.dumps(x) + "\n" for x in rows))
    elif damage == "seed":
        recorder = TickRecorder(tmp_path, 111, 222)
        worker = TickerWorker(None, 111, 222)
        state = {
            "version": 1,
            "builders": {t: builder_state(b) for t, b in worker.candles.items()},
            "counts": worker.candle_counts,
            "gap": False,
        }
        recorder.write("checkpoint", START, {"checkpoint": json.loads(encode(state))})
        paths = sorted(recorder.directory.glob("*.jsonl"))
    elif damage == "no_spot":
        recorder = TickRecorder(tmp_path, 111, 222)
        recorder.write("advance", START, {"gap": False})
        paths = sorted(recorder.directory.glob("*.jsonl"))
    calendar = (
        CALENDAR
        if damage != "wrong_calendar"
        else SessionCalendar(START.date(), START.date(), ())
    )
    with pytest.raises(TickFidelityError) as error:
        restore_tick_renko(
            paths,
            box=10,
            anchor=100,
            calendar=calendar,
            ordering_complete=damage != "no_attestation",
        )
    assert error.value.rebuild_required is True
