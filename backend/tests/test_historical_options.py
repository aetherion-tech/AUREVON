"""Replay option evidence cannot look ahead or borrow current contract identity."""

import hashlib
import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.market.historical_options import (
    CoverageRequest,
    HistoricalOptions,
    coverage,
    load_options,
)
from app.market.historical_replay_inputs import inspect_inputs, prepare_inputs
from app.tools.historical_option_coverage import main


def stamp(seconds: int = 0) -> datetime:
    return datetime.fromisoformat(f"2025-01-02T10:00:{seconds:02d}+05:30")


def payload():
    contract = dict(
        token=123,
        symbol="NIFTY25JAN23000CE",
        expiry="2025-01-30",
        strike="23000",
        option_type="CE",
        lot_size=75,
        tick_size="0.05",
    )
    return dict(
        price_basis="ACTUAL_RECORDED_DEPTH",
        provider="synthetic-test-fixture",
        source_reference="engineering-only-not-real-market-evidence",
        catalogs=[dict(loaded_at=stamp().isoformat(), contracts=[contract])],
        quotes=[
            dict(
                contract=contract.copy(),
                exchange_at=stamp(1).isoformat(),
                received_at=stamp(2).isoformat(),
                bids=[dict(price="100", quantity=150)],
                asks=[dict(price="100.05", quantity=150)],
                open_interest=100,
            )
        ],
    )


def test_availability_staleness_and_deterministic_seek():
    bundle = HistoricalOptions.model_validate(payload())
    assert bundle.quotes_at(stamp(1)) == {}
    assert bundle.quotes_at(stamp(2))[123].contract.lot_size == 75
    assert bundle.quotes_at(stamp(7)) == {}
    assert bundle.quotes_at(stamp(2))[123].bids[0].price == 100
    assert bundle.quotes_at(stamp()) == {}
    with pytest.raises(ValueError):
        bundle.quotes_at(datetime(2025, 1, 2))


@pytest.mark.parametrize(
    "mutation",
    [
        "future_exchange",
        "unknown_contract",
        "lot_change",
        "duplicate",
        "off_tick",
        "expired",
        "estimated",
        "float_price",
        "catalog_order",
    ],
)
def test_invalid_evidence_rejected(mutation):
    p = payload()
    q = p["quotes"][0]
    if mutation == "future_exchange":
        q["exchange_at"] = stamp(3).isoformat()
    elif mutation == "unknown_contract":
        q["contract"]["token"] = 124
    elif mutation == "lot_change":
        q["contract"]["lot_size"] = 25
    elif mutation == "duplicate":
        p["quotes"].append(q.copy())
    elif mutation == "off_tick":
        q["bids"][0]["price"] = "99.99"
    elif mutation == "expired":
        q["contract"]["expiry"] = "2024-12-31"
        p["catalogs"][0]["contracts"][0]["expiry"] = "2024-12-31"
    elif mutation == "estimated":
        p["price_basis"] = "ESTIMATED"
    elif mutation == "float_price":
        q["bids"][0]["price"] = 100.0
    else:
        p["catalogs"].append(p["catalogs"][0].copy())
    with pytest.raises(ValidationError):
        HistoricalOptions.model_validate(p)


def test_historical_snapshot_change_invalidates_old_identity():
    p = payload()
    new_contract = p["quotes"][0]["contract"] | {"lot_size": 25}
    p["catalogs"].append(dict(loaded_at=stamp(3), contracts=[new_contract]))
    bundle = HistoricalOptions.model_validate(p)
    assert bundle.quotes_at(stamp(2))[123].contract.lot_size == 75
    assert bundle.quotes_at(stamp(3)) == {}


def test_bounded_hash_and_honest_coverage(tmp_path):
    path = tmp_path / "options.json"
    raw = json.dumps(payload()).encode()
    path.write_bytes(raw)
    bundle, digest = load_options(path)
    assert digest == hashlib.sha256(raw).hexdigest()
    report = coverage(bundle, CoverageRequest(start=stamp(), end=stamp(3)))
    assert report["status"] == "INPUT_PRESENT_NOT_EXECUTION_READY"
    assert report["option_pnl"] is None
    request = CoverageRequest(start="2025-01-01T09:15:00+05:30", end=stamp())
    assert len(coverage(bundle, request)["blockers"]) == 2
    with pytest.raises(ValueError):
        load_options(path, max_bytes=3)
    with pytest.raises(ValidationError):
        CoverageRequest(start=stamp(3), end=stamp())


def test_isolated_durable_inputs_and_corruption(tmp_path):
    source = tmp_path / "source.json"
    original = json.dumps(payload())
    source.write_text(original)
    root = tmp_path / "replays"
    request = CoverageRequest(start=stamp(), end=stamp(3))
    first = prepare_inputs(source, request, root)
    second = prepare_inputs(source, request, root)
    assert first != second
    assert source.read_text() == original
    assert inspect_inputs(root, first)["entries_enabled"] is False
    (root / first / "options.json").write_text(original + " ")
    with pytest.raises(ValueError, match="integrity"):
        inspect_inputs(root, first)
    assert inspect_inputs(root, second)["coverage"]["option_pnl"] is None
    with pytest.raises(ValueError):
        inspect_inputs(root, "../source.json")


def test_invalid_import_does_not_publish_run(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text("{}")
    root = tmp_path / "replays"
    with pytest.raises(ValueError):
        prepare_inputs(source, CoverageRequest(start=stamp(), end=stamp(3)), root)
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("has_bundle", [False, True])
def test_cli_reports_evidence_without_enabling_entries(
    tmp_path, monkeypatch, capsys, has_bundle
):
    args = ["coverage", "--start", stamp().isoformat(), "--end", stamp(3).isoformat()]
    if has_bundle:
        source = tmp_path / "source.json"
        source.write_text(json.dumps(payload()))
        args += ["--bundle", str(source), "--runs-dir", str(tmp_path / "runs")]
    monkeypatch.setattr("sys.argv", args)
    main()
    result = json.loads(capsys.readouterr().out)
    if has_bundle:
        assert result["entries_enabled"] is False
        assert result["coverage"]["status"] == "INPUT_PRESENT_NOT_EXECUTION_READY"
    else:
        assert result["status"] == "BLOCKED"
        assert result["option_pnl"] is None
