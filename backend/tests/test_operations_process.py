"""Actual OS-process crash with isolated synthetic wallet/providers."""

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path


def test_process_crash_mid_position_restores_without_duplicate_fills_or_ledger(
    tmp_path,
):
    child = Path(__file__).with_name("ops_process_scenario.py")
    database = tmp_path / "crash.db"
    crashed = subprocess.run(
        [sys.executable, str(child), "crash", str(database)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert crashed.returncode == 71, crashed.stderr
    restored = subprocess.run(
        [sys.executable, str(child), "restore", str(database)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert restored.returncode == 0, restored.stderr
    result = json.loads(restored.stdout)
    assert result["positions"] == 1 and result["final_fills"] == 4
    assert Decimal(result["reserved"]) == 0
