"""Validate operator policy before any historical recovery can start."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_warmup_policy_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.warmup_lookback_trading_days == 20
    assert settings.recovery_max_gap_days == 30
    assert settings.recovery_max_attempts == 5
    assert settings.recovery_backoff_seconds == 1
    assert settings.recovery_backoff_max_seconds == 30
    assert settings.readiness_entry_delay_seconds == 60


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("WARMUP_LOOKBACK_TRADING_DAYS", "0"),
        ("WARMUP_LOOKBACK_TRADING_DAYS", "251"),
        ("WARMUP_LOOKBACK_TRADING_DAYS", "1.5"),
        ("RECOVERY_MAX_GAP_DAYS", "0"),
        ("RECOVERY_MAX_GAP_DAYS", "366"),
        ("RECOVERY_MAX_ATTEMPTS", "0"),
        ("RECOVERY_MAX_ATTEMPTS", "21"),
        ("RECOVERY_BACKOFF_SECONDS", "0"),
        ("RECOVERY_BACKOFF_SECONDS", "nan"),
        ("RECOVERY_BACKOFF_SECONDS", "inf"),
        ("RECOVERY_BACKOFF_MAX_SECONDS", "0"),
        ("RECOVERY_BACKOFF_MAX_SECONDS", "301"),
        ("RECOVERY_BACKOFF_MAX_SECONDS", "nan"),
        ("RECOVERY_BACKOFF_MAX_SECONDS", "inf"),
        ("READINESS_ENTRY_DELAY_SECONDS", "59"),
        ("READINESS_ENTRY_DELAY_SECONDS", "3601"),
    ],
)
def test_invalid_warmup_policy(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_environment_policy_and_backoff_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WARMUP_LOOKBACK_TRADING_DAYS", "25")
    monkeypatch.setenv("RECOVERY_MAX_GAP_DAYS", "45")
    monkeypatch.setenv("RECOVERY_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("RECOVERY_BACKOFF_SECONDS", "2.5")
    monkeypatch.setenv("RECOVERY_BACKOFF_MAX_SECONDS", "2.5")
    monkeypatch.setenv("READINESS_ENTRY_DELAY_SECONDS", "90")
    settings = Settings(_env_file=None)
    assert settings.warmup_lookback_trading_days == 25
    assert settings.recovery_max_gap_days == 45
    assert settings.recovery_max_attempts == 3
    assert settings.recovery_backoff_seconds == 2.5
    assert settings.recovery_backoff_max_seconds == 2.5
    assert settings.readiness_entry_delay_seconds == 90
    monkeypatch.setenv("RECOVERY_BACKOFF_MAX_SECONDS", "2")
    with pytest.raises(ValidationError, match="at least the initial delay"):
        Settings(_env_file=None)
