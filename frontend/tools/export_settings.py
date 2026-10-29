"""Generate UI rules from Pine/backend contracts without app, DB or env loading."""

import argparse
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "backend"))
from app.api.domain_contracts import SettingsBundle  # noqa: E402
from app.indicator.settings import INPUTS  # noqa: E402


def manifest() -> str:
    pine = (root / "docs/pine/renko_indicator.pine").read_text(encoding="utf-8")
    groups = dict(re.findall(r'^(\w+)\s*=\s*"([^"]+)"', pine, re.M))
    ui = {}
    for line in pine.splitlines():
        match = re.match(r"(\w+)\s*=\s*input\.\w+\(", line)
        if not match:
            continue
        name = match[1]
        quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', line)
        # The first quoted string is a default for string/symbol/timeframe inputs.
        label = (
            quoted[1]
            if INPUTS[name]["kind"] in ("string", "symbol", "timeframe")
            else quoted[0]
        )
        group = re.search(r'group\s*=\s*("[^"]+"|\w+)', line)[1]
        tooltip = re.search(r'tooltip\s*=\s*"((?:[^"\\]|\\.)*)"', line)
        ui[name] = dict(
            label=label,
            group=groups.get(group, group.strip('"')),
            help=tooltip[1].replace("\\n", " ") if tooltip else label,
        )
    assert set(ui) == set(INPUTS), "Every Pine input must have UI metadata"
    return (
        json.dumps(
            dict(
                schema=SettingsBundle.model_json_schema(mode="serialization"),
                pine=INPUTS,
                ui=ui,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = root / "frontend/src/settings-manifest.json"
    expected = manifest()
    if args.check:
        if target.read_text(encoding="utf-8") != expected:
            raise SystemExit(
                "Settings UI manifest drift; regenerate with tools/export_settings.py"
            )
        print("Settings UI/Pine contract parity passed")
    else:
        target.write_text(expected, encoding="utf-8")
        print("Generated settings UI contract")
