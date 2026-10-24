"""Record/replay tests use synthetic ticks and clocks; never open Kite sockets."""

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.broker.kite_ticker import TickerWorker
from app.market.tick_recording import RecordingError, TickRecorder
from app.tools.replay_ticks import main, replay_events

START = datetime.fromisoformat("2026-10-23T09:15:00+05:30")


def tick(token: int, ts: datetime, price: int, volume: int) -> dict:
    return {
        "instrument_token": token,
        "exchange_timestamp": ts,
        "last_price": price,
        "volume_traded": volume,
        "oi": volume * 2,
        "access_token": "must-not-be-recorded",
        "depth": {"private": "extra"},
    }


def test_recorded_replay_matches_live_candles_and_clock_events(tmp_path: Path) -> None:
    recorder = TickRecorder(tmp_path, 111, 222)
    worker = TickerWorker(None, 111, 222, recorder=recorder)
    for seconds, price, volume in [
        (0, 24000, 100),
        (30, 24050, 110),
        (60, 24100, 120),
        (299, 24150, 130),
        (300, 24200, 140),
        (300, 24250, 150),
    ]:
        at = START + timedelta(seconds=seconds)
        worker._accept(tick(111, at, price, volume), at)
        worker._accept(tick(222, at, price, volume), at)
    worker._disconnected()
    worker.advance_candles(START + timedelta(minutes=10))
    expected = [
        {"token": token, "candle": asdict(candle)}
        for token in worker.tokens
        for candle in worker.closed_candles[token]
    ]
    files = sorted(recorder.directory.glob("*.jsonl"))
    actual = list(replay_events(files))

    def key(result):
        return result["token"], result["candle"]["time"]

    assert sorted(actual, key=key) == sorted(expected, key=key)
    assert list(replay_events(files)) == actual
    text = files[0].read_text()
    assert "must-not-be-recorded" not in text
    assert "private" not in text and "depth" not in text
    assert len(text.splitlines()) == recorder.sequence == 13


def test_daily_rotation_ist_sequence_and_restart_isolation(tmp_path: Path) -> None:
    recorder = TickRecorder(tmp_path, 111, 222)
    # UTC date is still Friday, but IST has entered Saturday.
    recorder.write("advance", START, {"gap": False})
    recorder.write(
        "advance", datetime.fromisoformat("2026-10-23T19:00:00+00:00"), {"gap": True}
    )
    files = sorted(recorder.directory.glob("*.jsonl"))
    assert [p.name for p in files] == ["2026-10-23.jsonl", "2026-10-24.jsonl"]
    assert list(replay_events(files)) == []
    with pytest.raises(ValueError, match="sequence"):
        list(replay_events(files[1:]))
    other = TickRecorder(tmp_path, 111, 222)
    assert other.directory != recorder.directory


@pytest.mark.parametrize(
    "mutation",
    ["truncated", "sequence", "version", "session", "tokens", "timestamp", "tick"],
)
def test_corrupt_recordings_fail(tmp_path: Path, mutation: str) -> None:
    recorder = TickRecorder(tmp_path, 111, 222)
    recorder.write("advance", START, {"gap": False})
    recorder.write("advance", START, {"gap": False})
    path = next(recorder.directory.glob("*.jsonl"))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if mutation == "sequence":
        rows[1]["sequence"] = 3
    elif mutation == "version":
        rows[1]["version"] = 2
    elif mutation == "session":
        rows[1]["session"] = "different"
    elif mutation == "tokens":
        rows[1]["spot_token"] = 333
    elif mutation == "timestamp":
        rows[1]["at"] = "2026-10-23T09:15:00"
    elif mutation == "tick":
        rows[1].update(
            kind="tick",
            token=111,
            price="NaN",
            volume=None,
            oi=None,
            exchange_time=START.isoformat(),
        )
    text = "\n".join(json.dumps(row) for row in rows) + "\n"
    path.write_text(text + ("{" if mutation == "truncated" else ""))
    with pytest.raises(ValueError, match="invalid recording"):
        list(replay_events([path]))


def test_disk_failure_has_safe_message(
    tmp_path: Path,
) -> None:
    recorder = TickRecorder(tmp_path, 111, 222)
    with patch.object(Path, "open", side_effect=OSError("private disk details")):
        with pytest.raises(RecordingError, match="Cannot write") as error:
            recorder.write("advance", START, {"gap": False})
    assert "private" not in str(error.value)


@pytest.mark.asyncio
async def test_failed_consumer_still_closes_socket(tmp_path: Path) -> None:
    import asyncio

    recorder = TickRecorder(tmp_path, 111, 222)
    worker = TickerWorker(Mock(), 111, 222, recorder=recorder)
    with patch("twisted.internet.reactor.callFromThread") as close:
        await worker.start()
        worker._enqueue(
            [tick(111, START, 24000, 100), tick(222, START, 24000, 100)], START
        )
        with patch.object(
            recorder, "write", side_effect=RecordingError("Cannot write")
        ):
            with pytest.raises(RecordingError):
                await asyncio.wait_for(worker.stop(), timeout=2)
        assert close.call_count == 2


@pytest.mark.asyncio
async def test_shutdown_drains_accepted_queue(tmp_path: Path) -> None:
    recorder = TickRecorder(tmp_path, 111, 222)
    worker = TickerWorker(Mock(), 111, 222, recorder=recorder)
    with patch("twisted.internet.reactor.callFromThread"):
        await worker.start()
        worker._enqueue([tick(111, START, 24000, 100)], START)
        await worker.stop()
    assert recorder.sequence == 1
    assert worker.accepted == 1


def test_empty_and_cli_failures(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    assert main([str(path)]) == 1
    assert main([str(tmp_path / "missing")]) == 1
