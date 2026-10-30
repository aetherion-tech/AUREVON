"""Build an append-only reference debug copy without editing the original Pine."""

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL_SHA256 = "d1b4e220a8e575c3e6839ca5e2058d2de190ee56fcf308ccf31e7864088170b2"
FIELDS = {
    "index": "bar_index",
    "confirmed": "barstate.isconfirmed ? 1 : 0",
    "rsi": "rsi",
    "supertrend": "st",
    "direction": "dir",
    "bias_score": "biasScore",
    "bias_direction": "biasDir",
    "flow_score": "flowScore",
    "flow_ok": "flowOk ? 1 : 0",
    "run_len": "runLen",
    "sig_long": "sigL ? 1 : 0",
    "sig_short": "sigS ? 1 : 0",
    "type_long": "ref_type_code(typL)",
    "type_short": "ref_type_code(typS)",
    "grade_long": "gL",
    "grade_short": "gS",
    "entry_long": "entL ? 1 : 0",
    "entry_short": "entS ? 1 : 0",
    "exit_now": "exitNow ? 1 : 0",
    "t1_now": "t1Now ? 1 : 0",
    "exit_direction": "exitDir",
    "exit_type": "ref_type_code(exitTyp)",
    "position_direction": "posDir",
    "position_type": "ref_type_code(posType)",
    "trade_seq": "tradeSeq",
    "active_id": "ref_id_number(posId)",
    "exit_id": "exitNow ? ref_id_number(exitId) : na",
    "t1_id": "t1Now ? ref_id_number(posId[1]) : na",
    "t1_type": "t1Now ? ref_type_code(posType[1]) : 0",
    "t1_direction": "t1Now ? posDir[1] : 0",
}
SUFFIX = """
// REF DEBUG: appended observations only; original bytes above are unchanged.
// Type: 0 none, 1 CORE, 2 DIV, 3 HDIV, 4 PB, 5 BRK, 6 TRAP, 7 ORB, 8 SRG.
// Numeric IDs reversibly encode the five characters inside the original [ID].
ref_type_code(string typ) =>
    switch typ
        "CORE" => 1
        "DIV" => 2
        "HDIV" => 3
        "PB" => 4
        "BRK" => 5
        "TRAP" => 6
        "ORB" => 7
        "SRG" => 8
        => 0

ref_id_number(string value) =>
    int result = na
    if str.length(value) == 7
        string alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789#@$%&*+!"
        result := 0
        for i = 1 to 5
            int digit = str.pos(alphabet, str.substring(value, i, i + 1))
            result := result * 40 + digit
    result

"""


def build(source: bytes) -> bytes:
    if hashlib.sha256(source).hexdigest() != ORIGINAL_SHA256:
        raise ValueError(
            "Original Pine changed; review debug bindings before generation"
        )
    plots = "\n".join(
        f'plot({expression}, "ref_{name}", display=display.data_window, precision=12)'
        for name, expression in FIELDS.items()
    )
    return source + (SUFFIX + plots + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "docs/pine/renko_indicator_debug.pine"
    generated = build((ROOT / "docs/pine/renko_indicator.pine").read_bytes())
    if args.check:
        if not path.is_file() or path.read_bytes() != generated:
            raise SystemExit(
                "Debug copy drifted; preserve original and review bindings"
            )
        print("Original hash and append-only debug copy verified; Pine not compiled")
    else:
        with path.open("xb") as stream:
            stream.write(generated)
        print(f"Created {path}; {len(FIELDS)} debug plots; Pine not compiled")


if __name__ == "__main__":
    main()
