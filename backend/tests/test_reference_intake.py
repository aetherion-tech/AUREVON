"""Synthetic intake checks; these fixtures never serve as reference acceptance."""

import csv
import hashlib
import io
import json

import pytest

from app.tools.reference_debug import FIELDS, ORIGINAL_SHA256, ROOT, build
from app.tools.reference_export import decode_id, intake, normalize, timestamp


def export(rows=2, *, index_start=0, confirmed=1, stamp="2026-10-28T10:00:00+05:30"):
    stream = io.StringIO(newline="")
    columns = ["time", "open", "high", "low", "close", *(f"ref_{k}" for k in FIELDS)]
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for i in range(rows):
        row = dict.fromkeys(columns, "0")
        row.update(time=stamp, open="100", high="150", low="100", close="150")
        row.update(ref_index=str(i + index_start), ref_confirmed=str(confirmed))
        row.update(ref_rsi="na", ref_supertrend="123.45678901", ref_direction="1")
        writer.writerow(row)
    return stream.getvalue().encode()


def test_debug_is_byte_exact_prefix_and_observations_only():
    original = (ROOT / "docs/pine/renko_indicator.pine").read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256
    generated = build(original)
    assert generated == (ROOT / "docs/pine/renko_indicator_debug.pine").read_bytes()
    assert generated.startswith(original)
    suffix = generated[len(original) :].decode()
    assert suffix.count("\nplot(") == 30
    assert "request." not in suffix and "alert(" not in suffix
    # Conservative upper bound: original plot calls <=2 counts each, fills
    # <=1 each, bgcolor <=1, 22 alertconditions; debug plots use constant color.
    assert 4 * 2 + 2 + 1 + 22 + len(FIELDS) <= 64
    with pytest.raises(ValueError, match="Original Pine changed"):
        build(original + b"\n")


def test_equal_timestamp_bricks_keep_order_and_reference_values(tmp_path):
    source = tmp_path / "source.csv"
    raw = export()
    source.write_bytes(raw)
    output = tmp_path / "new"
    report = intake(source, output)
    assert source.read_bytes() == raw == (output / "original.csv").read_bytes()
    with (output / "math.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [r["index"] for r in rows] == ["0", "1"]
    assert rows[0]["time"] == rows[1]["time"]
    assert rows[0]["supertrend"] == "123.45678901"
    assert rows[0]["rsi"] == ""
    assert report["reference_verified"] is False
    assert report["formal_sessions"] == 0
    assert report["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert json.loads((output / "manifest.json").read_text()) == report
    with pytest.raises(ValueError, match="immutable"):
        intake(source, output)


@pytest.mark.parametrize(
    "raw", [export(index_start=5), export(confirmed=0), export(rows=0)]
)
def test_invalid_evidence_creates_no_output(tmp_path, raw):
    source = tmp_path / "input.csv"
    source.write_bytes(raw)
    output = tmp_path / "new"
    with pytest.raises(ValueError):
        intake(source, output)
    assert not output.exists()
    assert source.read_bytes() == raw


def test_prefixed_titles_work_and_duplicate_indicators_are_rejected():
    raw = export()
    prefixed = raw.replace(b"ref_rsi", b"Indicator: ref_rsi")
    assert normalize(prefixed)[0]["rsi"] == ""
    with pytest.raises(ValueError, match="ambiguous"):
        normalize(raw.replace(b"ref_rsi", b"ref_rsi,Indicator: ref_rsi", 1))


def test_naive_timestamp_and_reordered_history_are_rejected():
    with pytest.raises(ValueError, match="timezone"):
        timestamp("2026-10-28T10:00:00")
    assert timestamp("1793152800") == timestamp("1793152800000")
    raw = export().decode().splitlines()
    raw[2] = raw[2].replace("10:00:00", "09:00:00")
    with pytest.raises(ValueError, match="out of order"):
        normalize(("\n".join(raw) + "\n").encode())


def test_trade_ids_decode_original_symbols_without_sequence_guessing():
    assert decode_id("0") == "[AAAAA]"
    assert decode_id(str(40**5 - 1)) == "[!!!!!]"
    assert decode_id("") == ""
    for invalid in ("0.5", "-1", str(40**5), "Infinity"):
        with pytest.raises(ValueError):
            decode_id(invalid)
