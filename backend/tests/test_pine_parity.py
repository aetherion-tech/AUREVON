"""Full parity transport/report regressions, not real TradingView acceptance."""

import csv
import json
from datetime import timedelta

import pytest
from alembic.config import Config
from sqlalchemy import inspect
from test_pine_strategy import at, brick, settings

from alembic import command
from app.db.session import database_engine
from app.indicator.full_parity import compare_full, first_difference, projection
from app.indicator.strategy import PineContext, PineEngine
from app.indicator.text import number_text


def fixture_rows():
    s = settings(atrLen=2, rsiLen=2)
    engine = PineEngine("reference", s)
    prices = [1000, 1050, 1100, 1150, 1100, 1050, 1000, 1050]
    rows = []
    for i in range(len(prices) - 1):
        b = brick(i, prices[i], prices[i + 1])
        result = projection(engine.process(b))
        row = {
            "index": i,
            "time": b.ts.isoformat(),
            "open": str(b.open),
            "high": str(b.high),
            "low": str(b.low),
            "close": str(b.close),
            "context": "{}",
            "futures": "[]",
        }
        row.update(
            {
                k: json.dumps(v) if isinstance(v, list) else v if v is not None else ""
                for k, v in result.items()
            }
        )
        rows.append(row)
    return s, rows


def write(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_full_export_roundtrip_and_insufficient_days(tmp_path):
    s, rows = fixture_rows()
    path = tmp_path / "debug.csv"
    write(path, rows)
    result = compare_full(path, s)
    assert result["passed"] and result["bricks"] == 7
    assert len(result["provenance"]["sha256"]) == 64
    result = compare_full(path, s, required_days=10)
    assert not result["passed"]
    assert result["reason"] == "insufficient_reference_days"


@pytest.mark.parametrize(
    "field",
    [
        "rsi",
        "supertrend",
        "direction",
        "bias_score",
        "bias_direction",
        "flow_score",
        "signals",
        "events",
    ],
)
def test_full_first_divergence_each_required_series(tmp_path, field):
    s, rows = fixture_rows()
    path = tmp_path / "debug.csv"
    if field in ("signals", "events"):
        rows[3][field] = '[{"unexpected":"mismatch"}]'
    else:
        rows[3][field] = 999
    write(path, rows)
    result = compare_full(path, s)
    assert not result["passed"] and result["index"] == 3
    assert result["column"] == (
        field + "[0]" if field in ("signals", "events") else field
    )


def test_independent_futures_flow_is_calculated_not_reference_input(tmp_path):
    s, rows = fixture_rows()
    path = tmp_path / "debug.csv"
    first = {
        "contract": "NIFTY_OCT",
        "start": (at() - timedelta(minutes=5)).isoformat(),
        "end": at().isoformat(),
        "high": 101,
        "low": 99,
        "close": 100,
        "volume": 10,
        "oi": 100,
        "previous_close": 90,
        "previous_oi": 90,
    }
    rows[0]["futures"] = json.dumps([first])
    # fPxPct is still unavailable; VWAP-side=0, day direction adds +1.
    rows[0]["flow_score"] = 1
    rows[0]["bias_score"] += 1  # fFlow also contributes +1 to the ten-factor score.
    write(path, rows)
    result = compare_full(path, s)
    assert result["index"] > 0  # first independently known flow score matched
    rows[0]["context"] = json.dumps({"flow_score": 1})
    write(path, rows)
    with pytest.raises(ValueError, match="independent"):
        compare_full(path, s)


def test_future_source_context_and_wicks_are_rejected(tmp_path):
    s, rows = fixture_rows()
    path = tmp_path / "debug.csv"
    rows[0]["context"] = json.dumps(
        {"available_at": at(1).isoformat(), "day_open": 1000}
    )
    write(path, rows)
    with pytest.raises(ValueError, match="unavailable"):
        compare_full(path, s)
    rows[0]["context"] = "{}"
    rows[0]["high"] = 9999
    write(path, rows)
    with pytest.raises(ValueError, match="wick"):
        compare_full(path, s)


def test_nested_event_id_exact_numeric_tolerance_and_type_checks():
    assert first_difference({"rsi": 50.0}, {"rsi": 50.000000001}, 1e-8) is None
    assert (
        first_difference({"direction": 1}, {"direction": 1.01}, 1)["column"]
        == "direction"
    )
    assert (
        first_difference([{"trade_id": "[AAAAA]"}], [{"trade_id": "[AAAAB]"}], 1)[
            "column"
        ]
        == "[0].trade_id"
    )
    assert first_difference(True, 1, 0) is not None
    assert number_text(2.5, "#") == "3"
    assert number_text(12.0, "#.#") == "12"


def test_parity_cli_writes_report(tmp_path, monkeypatch, capsys):
    from app.indicator.parity import main

    s, rows = fixture_rows()
    path = tmp_path / "debug.csv"
    write(path, rows)
    config = tmp_path / "inputs.json"
    config.write_text(json.dumps(s.values))
    report = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "parity",
            str(path),
            "--full",
            "--settings",
            str(config),
            "--report",
            str(report),
        ],
    )
    assert main() == 0
    assert json.loads(report.read_text())["passed"]
    assert json.loads(capsys.readouterr().out)["passed"]


def test_migration_preserves_previous_schema_and_downgrades(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "0006_dashboard_api")
    db = database_engine(url)
    try:
        before = set(inspect(db).get_table_names())
        command.upgrade(cfg, "0007_indicator")
        assert set(inspect(db).get_table_names()) == before | {
            "indicator_checkpoints",
            "indicator_results",
            "indicator_events",
        }
        command.downgrade(cfg, "0006_dashboard_api")
        assert set(inspect(db).get_table_names()) == before
        command.upgrade(cfg, "0007_indicator")
    finally:
        db.dispose()


@pytest.mark.parametrize("damage", ["bucket", "history", "pending", "active"])
def test_corrupt_strategy_restart_fails_closed(damage):
    engine = PineEngine("test", settings())
    engine.process(brick(0, 100, 150))
    snapshot = engine.snapshot()
    if damage == "bucket":
        snapshot["history"][0]["bucket"] = 99
    elif damage == "history":
        snapshot["history"] = []
    elif damage == "pending":
        snapshot["base"]["variables"]["pBar"] = [1]
    else:
        snapshot["base"]["variables"]["posDir"] = 1
    with pytest.raises(ValueError):
        PineEngine.restore(snapshot, "test", engine.base.settings)


def test_source_context_bridge_missing_oi_and_future_flow():
    daily = {"open": "1000", "previous_close": None, "high": "1050", "low": "1000"}
    flow = {
        "completed_at": at().isoformat(),
        "price_pct": 1,
        "volume_spike": True,
        "flow_ok": True,
        "score": 3,
        "vwap_side": 1,
    }
    context = PineContext.from_market(daily, at(), flow)
    assert context.day_open == 1000 and context.previous_close is None
    assert context.volume_side == 1
    with pytest.raises(ValueError, match="future"):
        PineContext.from_market(daily, at(), flow | {"completed_at": at(1).isoformat()})
