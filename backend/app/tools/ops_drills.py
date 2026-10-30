"""Retain repeatable synthetic operational drill results; never approve G4/G5."""

import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from app.config import BACKEND_DIR

GROUPS = {
    "QA-19-11": [
        "tests/test_ticker.py",
        "tests/test_readiness.py",
        "tests/test_market_service.py",
    ],
    "QA-19-12": ["tests/test_operations_process.py", "tests/test_paper_execution.py"],
    "QA-19-13": ["tests/test_domain_api.py", "tests/test_paper_execution.py"],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--all-tests", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new evidence file; prior drill records are immutable")
    paths = sorted({path for group in GROUPS.values() for path in group})
    if args.all_tests:
        paths = ["tests"]
    with tempfile.TemporaryDirectory(prefix="aurevon-drills-") as folder:
        junit = Path(folder) / "results.xml"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *paths, "-q", f"--junitxml={junit}"],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        cases = []
        if junit.is_file():
            for case in ET.parse(junit).iter("testcase"):
                state = (
                    "FAIL"
                    if case.find("failure") is not None
                    or case.find("error") is not None
                    else "SKIP"
                    if case.find("skipped") is not None
                    else "PASS"
                )
                cases.append(
                    {
                        "class": case.attrib.get("classname"),
                        "case": case.attrib.get("name"),
                        "seconds": float(case.attrib.get("time", "0")),
                        "status": state,
                    }
                )
        report = {
            "at": datetime.now(timezone.utc).isoformat(),
            "evidence": "ISOLATED_SYNTHETIC_DRILLS",
            "qualifying_exchange_sessions": 0,
            "formal_g5_accepted": False,
            "groups": GROUPS,
            "exit_code": result.returncode,
            "cases": cases,
            "note": (
                "Injected providers/socket events and an isolated process crash; "
                "no operator state or actual market-session claim."
            ),
        }
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
    print(
        json.dumps(
            {
                "exit_code": result.returncode,
                "cases": len(cases),
                "report": str(args.output),
            }
        )
    )
    raise SystemExit(result.returncode or (0 if cases else 1))


if __name__ == "__main__":
    main()
