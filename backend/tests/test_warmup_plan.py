"""Calendar and completed-candle boundaries for cold starts and restarts."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.broker.kite_auth import IST
from app.config import Settings
from app.market.warmup import (
    CheckpointBoundaries,
    Session,
    SessionCalendar,
    plan_history,
)


def ts(day: int, hour: int = 9, minute: int = 15) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=IST)


def calendar() -> SessionCalendar:
    # Synthetic holiday on Friday 23 and special Sunday session on 25.
    return SessionCalendar(
        date(2026, 10, 19),
        date(2026, 10, 26),
        tuple(Session(ts(d), ts(d, 15, 30)) for d in (19, 20, 21, 22, 25, 26)),
    )


def settings() -> Settings:
    return Settings(_env_file=None, warmup_lookback_trading_days=2)


def test_cold_start_completed_bars_and_context() -> None:
    plan = plan_history(settings(), calendar(), ts(26, 9, 22))
    assert [r.start.day for r in plan.spot] == [22, 25, 26]
    assert plan.spot[-1].end == ts(26, 9, 21)
    assert plan.spot[-1].completed_through == ts(26, 9, 22)
    assert plan.futures[-1].end == ts(26)
    assert plan.futures[-1].completed_through == ts(26, 9, 20)
    assert plan.previous_session == date(2026, 10, 25)
    assert plan.entries_enabled is False


@pytest.mark.parametrize(
    "hour,minute,last_day", [(8, 0, 25), (9, 15, 25), (15, 30, 26), (19, 0, 26)]
)
def test_session_boundaries(hour: int, minute: int, last_day: int) -> None:
    plan = plan_history(settings(), calendar(), ts(26, hour, minute))
    assert plan.spot[-1].end.day == last_day
    assert plan.previous_session == date(2026, 10, 25)
    assert all(r.completed_through <= plan.cutoff for r in (*plan.spot, *plan.futures))


def test_restart_and_timezone_equivalence() -> None:
    checkpoint = CheckpointBoundaries(ts(26, 11, 58), ts(26, 11, 55))
    plan = plan_history(settings(), calendar(), ts(26, 12, 2), checkpoint)
    assert plan.mode == "checkpoint_restart"
    assert plan.spot[0].start == ts(26, 11, 58)
    assert plan.futures[0].start == ts(26)
    assert plan.futures[-1].end == ts(26, 11, 55)
    assert plan == plan_history(
        settings(), calendar(), ts(26, 12, 2).astimezone(UTC), checkpoint
    )


def test_holiday_restart_with_independent_boundaries() -> None:
    plan = plan_history(
        settings(),
        calendar(),
        ts(24, 12, 0),
        CheckpointBoundaries(ts(21, 15, 29), ts(22, 10, 0)),
    )
    assert [r.start.day for r in plan.spot] == [21, 22]
    assert plan.futures[0].start == ts(22, 10, 0)


@pytest.mark.parametrize(
    "spot,future",
    [
        (ts(26, 13), ts(26)),
        (ts(26).replace(tzinfo=None), ts(26)),
        (ts(26).replace(second=1), ts(26)),
        (ts(26), ts(26, 9, 16)),
        (ts(19) - timedelta(days=40), ts(26)),
        (ts(19) - timedelta(days=1), ts(26)),
    ],
)
def test_invalid_checkpoint_fails(spot: datetime, future: datetime) -> None:
    with pytest.raises(ValueError):
        plan_history(
            settings(), calendar(), ts(26, 12), CheckpointBoundaries(spot, future)
        )


def test_insufficient_coverage_and_lookback() -> None:
    for cutoff in (ts(19, 8), ts(26).replace(tzinfo=None), ts(27)):
        with pytest.raises(ValueError):
            plan_history(settings(), calendar(), cutoff)
    with pytest.raises(ValueError, match="lookback"):
        plan_history(Settings(_env_file=None), calendar(), ts(26))


def test_bad_calendar_and_insufficient_futures_context() -> None:
    with pytest.raises(ValueError):
        Session(ts(26, 9, 16), ts(26, 15, 30))
    with pytest.raises(ValueError):
        SessionCalendar(
            date(2026, 10, 19),
            date(2026, 10, 26),
            (Session(ts(26), ts(26, 15, 30)),) * 2,
        )
    short = SessionCalendar(
        date(2026, 10, 19), date(2026, 10, 26), (Session(ts(25), ts(25, 9, 20)),)
    )
    with pytest.raises(ValueError, match="21 futures bars"):
        plan_history(
            Settings(_env_file=None, warmup_lookback_trading_days=1), short, ts(26, 8)
        )
