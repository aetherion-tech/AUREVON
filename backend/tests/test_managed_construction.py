"""Profile selection and calendar stability never imply reference acceptance."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.db.session import database_engine
from app.market.construction import managed_store
from app.market.exchange_calendar import ExchangeCalendar


@pytest.mark.parametrize("value", [1, 5, "1", "5"])
def test_source_minutes_accepts_exact_config_or_environment_values(value):
    s = Settings(_env_file=None, renko_source_minutes=value)
    assert s.renko_source_minutes == int(value)


@pytest.mark.parametrize("value", [True, False, 2, 0, 5.0, "05", "tick"])
def test_source_minutes_rejects_invalid_or_ambiguous_profile(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, renko_source_minutes=value)


def test_annual_identity_is_stable_when_warmup_window_moves():
    settings = Settings(_env_file=None, renko_anchor=22700, renko_source_minutes=5)
    calendar = ExchangeCalendar(settings.market_calendar_dir)
    engine = database_engine("sqlite://")
    try:
        first = managed_store(
            engine,
            settings,
            "test",
            111,
            222,
            calendar.window(datetime.fromisoformat("2026-10-23T11:00:00+05:30")),
        )
        later = managed_store(
            engine,
            settings,
            "test",
            111,
            222,
            calendar.window(datetime.fromisoformat("2026-10-26T11:00:00+05:30")),
        )
        assert first.configuration == later.configuration
        assert first.renko.calendar.first_date.isoformat() == "2026-01-01"
    finally:
        engine.dispose()
