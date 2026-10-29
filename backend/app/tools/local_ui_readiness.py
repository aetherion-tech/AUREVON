"""Read-only local UI milestone report. Does not activate paper execution."""

import argparse
import json
import re
from pathlib import Path
from typing import Any


def readiness(root: Path) -> dict[str, Any]:
    readme = (root / "README.md").read_text(encoding="utf-8")
    statuses = dict(
        re.findall(
            r"^\| ([A-Z]+-\d\d-\d\d) \| (Completed|Pending) \|", readme, re.MULTILINE
        )
    )
    groups = {
        "wallet_accounting": [f"BE-12-{n:02d}" for n in range(1, 13)],
        "domain_apis": [f"BE-13-{n:02d}" for n in range(6, 15)] + ["BE-13-20"],
        "ui_shell_auth_controls": [f"FE-14-{n:02d}" for n in range(1, 16)],
        "ui_positions_signals_exits": [f"FE-15-{n:02d}" for n in range(1, 16)],
        "ui_wallet": [f"FE-17-{n:02d}" for n in (1, 2, 3, 4, 6, 7, 8)],
        "ui_risk_settings": [f"FE-18-{n:02d}" for n in range(1, 12)],
        "reference_and_paper_gates": [
            "BE-08-14",
            "QA-09-19",
            "QA-09-20",
            "QA-11-15",
            "QA-11-16",
        ],
    }
    missing = {
        name: [task for task in tasks if statuses.get(task) != "Completed"]
        for name, tasks in groups.items()
    }
    source = (root / "frontend" / "package.json").is_file()
    built = (root / "frontend" / "dist" / "index.html").is_file()
    blocked = any(missing.values()) or not source or not built
    return dict(
        status="BLOCKED" if blocked else "READY_FOR_OPERATOR_CHECK",
        paper_trading_ready=False,
        runtime="NOT_CHECKED",
        frontend_source_present=source,
        frontend_build_present=built,
        pending=missing,
        next_code=next(
            (tasks[0] for tasks in missing.values() if tasks),
            "operator runtime verification",
        ),
        instructions="docs/operations/local-paper-ui.md",
        note=(
            "Task completion and a build do not prove runtime readiness. "
            "Check PAPER mode, feed, execution wiring, close/kill and ledger. "
            "This command provides no background monitoring."
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    args = parser.parse_args()
    print(json.dumps(readiness(args.root), indent=2))


if __name__ == "__main__":
    main()
