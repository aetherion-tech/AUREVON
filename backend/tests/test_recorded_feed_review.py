import json
from datetime import datetime, timedelta

import pytest

from app.broker.kite_auth import IST
from app.market.historical import Candle, save_csv
from app.tools.recorded_feed_review import digest, historical_rows, review


@pytest.fixture
def sources(tmp_path):
    at = datetime(2026, 10, 30, 10, 0, tzinfo=IST)
    events = []

    def record(kind, seconds, **payload):
        events.append(
            {
                "version": 1,
                "sequence": len(events),
                "session": "test-recording",
                "spot_token": 111,
                "future_token": 222,
                "kind": kind,
                "at": (at + timedelta(seconds=seconds)).isoformat(),
                "gap": False,
                "gaps": [],
                **payload,
            }
        )

    record("advance", 0)
    for token, price, vol in [(111, "100", None), (222, "200", "1000")]:
        record(
            "tick",
            1,
            token=token,
            price=price,
            exchange_time=at.isoformat(),
            volume=vol,
            oi="500" if token == 222 else None,
        )
    for token, price, vol in [(111, "105", None), (222, "205", "1100")]:
        record(
            "tick",
            299,
            token=token,
            price=price,
            exchange_time=(at + timedelta(seconds=299)).isoformat(),
            volume=vol,
            oi="510" if token == 222 else None,
        )
    record("advance", 298)  # Captured earlier; file sequence must remain authoritative.
    record("advance", 300)
    record(
        "tick",
        301,
        token=111,
        price="106",
        exchange_time=(at + timedelta(seconds=301)).isoformat(),
        volume=None,
        oi=None,
    )
    path = tmp_path / "ticks.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    spot, future = tmp_path / "spot.csv", tmp_path / "future.csv"
    from decimal import Decimal as D

    save_csv(
        spot,
        [
            Candle(at, D(100), D(100), D(100), D(100), D(0), None),
            Candle(
                at + timedelta(minutes=4), D(105), D(105), D(105), D(105), D(0), None
            ),
        ],
        "minute",
    )
    save_csv(
        future, [Candle(at, D(200), D(205), D(200), D(205), D(100), D(510))], "5minute"
    )
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "status": "PASS",
                "evidence": "SYNTHETIC_TEST_ONLY",
                "spot": {"token": 111, "csv_sha256": digest(spot)},
                "future": {"token": 222, "csv_sha256": digest(future)},
            }
        ),
        encoding="utf-8",
    )
    return path, spot, future, receipt


def test_real_order_review_keeps_partial_vwap_unknown_capture_and_unfinished_tail(
    sources,
):
    path, spot, future, receipt = sources
    before = {p: digest(p) for p in sources}
    report = review([path], spot, future, receipt)
    assert report["deterministic_completed_candles"]
    assert report["completed_candles"] == 3
    assert report["event_time_regressions"] == [
        {"sequence": 5, "kind": "advance", "delta_ms": -1000}
    ]
    assert report["connected_at_capture"] is None
    assert report["queue_drops_at_capture"] is None
    assert report["formal_sessions"] == report["broker_calls"] == 0
    assert 111 in report["unfinished_tail"]
    future_row = next(c for c in report["comparisons"] if c["token"] == 222)
    assert future_row["live_minus_historical"]["volume"] == 0
    assert future_row["live_minus_historical"]["oi"] == 0
    assert future_row["vwap_partial"] and not future_row["vwap_comparable"]
    spot_row = next(c for c in report["comparisons"] if c["token"] == 111)
    assert spot_row["vwap_delta"] is None and not spot_row["vwap_comparable"]
    assert "unavailable" in spot_row["vwap_reason"]
    assert before == {p: digest(p) for p in sources}


def test_changed_historical_hash_is_rejected(sources):
    path, spot, future, receipt = sources
    spot.write_text(spot.read_text() + "\n")
    with pytest.raises(ValueError, match="hash changed"):
        review([path], spot, future, receipt)


def test_recording_sequence_gap_is_not_sorted_or_filled(sources):
    path, spot, future, receipt = sources
    lines = path.read_text().splitlines()
    del lines[2]
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="sequence"):
        review([path], spot, future, receipt)


def test_instrument_identity_mismatch_is_rejected(sources):
    path, spot, future, receipt = sources
    data = json.loads(receipt.read_text())
    data["future"]["token"] = 333
    receipt.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="identities differ"):
        review([path], spot, future, receipt)


def test_reversed_historical_order_is_not_accepted(sources):
    _, spot, _, _ = sources
    lines = spot.read_text().splitlines()
    spot.write_text("\n".join([lines[0], *reversed(lines[1:])]) + "\n")
    with pytest.raises(ValueError, match="times duplicate or invalid"):
        historical_rows(spot)
