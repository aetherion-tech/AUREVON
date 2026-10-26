"""Versioned annual exchange calendars; uncovered years never imply weekdays."""

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app.broker.kite_auth import IST
from app.market.warmup import Session, SessionCalendar, local_time


class CalendarError(RuntimeError):
    pass


class ExchangeCalendar:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def year(self, year: int) -> SessionCalendar:
        try:
            data = json.loads((self.directory / f"nse_{year}.json").read_text())
            if data["year"] != year or not data["sources"] or not data["reviewed_on"]:
                raise ValueError("Calendar provenance required")
            holidays = {date.fromisoformat(d) for d in data["holidays"]}
            special = data["special_sessions"]
            if any(d.year != year for d in holidays) or any(
                date.fromisoformat(d).year != year for d in special
            ):
                raise ValueError("Calendar dates outside year")
            sessions = []
            day = date(year, 1, 1)
            while day.year == year:
                override = special.get(day.isoformat())
                if override is not None:
                    if not override["source"]:
                        raise ValueError("Special session needs a source")
                    start, end = override["open"], override["close"]
                elif day.weekday() < 5 and day not in holidays:
                    start, end = data["normal_open"], data["processing_close"]
                else:
                    day += timedelta(days=1)
                    continue
                sessions.append(
                    Session(
                        datetime.combine(day, time.fromisoformat(start), IST),
                        datetime.combine(day, time.fromisoformat(end), IST),
                    )
                )
                day += timedelta(days=1)
            return SessionCalendar(
                date(year, 1, 1), date(year, 12, 31), tuple(sessions)
            )
        except (OSError, ValueError, TypeError, KeyError):
            raise CalendarError("Missing or invalid sourced annual calendar") from None

    def window(self, at: datetime, *, days: int = 90) -> SessionCalendar:
        at = local_time(at)
        first = at.date() - timedelta(days=days)
        years = [self.year(year) for year in range(first.year, at.year + 1)]
        return SessionCalendar(
            first,
            years[-1].last_date,
            tuple(
                session
                for annual in years
                for session in annual.sessions
                if session.opening.date() >= first
            ),
        )

    def session(self, at: datetime) -> Session | None:
        at = local_time(at)
        return next(
            (s for s in self.year(at.year).sessions if s.opening.date() == at.date()),
            None,
        )
