"""Audit both committed dependency graphs; retain failures without hiding findings."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    reports = root / "docs" / "testing"
    outcomes: list[dict[str, Any]] = []
    for name, cwd, command in (
        (
            "backend",
            root / "backend",
            ["uv", "audit", "--locked", "--output-format", "json"],
        ),
        ("frontend", root / "frontend", ["npm.cmd", "audit", "--json"]),
    ):
        executable = shutil.which(command[0])
        if executable is None:
            outcomes.append({"target": name, "status": "TOOL_MISSING"})
            continue
        result = subprocess.run(
            [executable, *command[1:]],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
        try:
            report = json.loads(result.stdout)
        except ValueError:
            outcomes.append({"target": name, "status": "AUDIT_UNAVAILABLE"})
            continue
        path = reports / f"OPS-19-{name}-audit.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        outcomes.append(
            {"target": name, "exit_code": result.returncode, "report": path.name}
        )
    print(json.dumps(outcomes, indent=2))
    if len(outcomes) != 2 or any(item.get("exit_code") != 0 for item in outcomes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
