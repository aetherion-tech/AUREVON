from datetime import datetime, timedelta

import pytest

from app.broker.kite_auth import IST
from app.tools.historical_acceptance import verify


class Provider:
    def __init__(self, gap=False, conflict=False, missing_oi=False):
        self.calls = 0
        self.gap, self.conflict, self.missing_oi = gap, conflict, missing_oi

    def historical_data(self, token, interval, start, end, *, oi=False):
        self.calls += 1
        step = timedelta(minutes=1 if interval == "minute" else 5)
        rows = []
        at = start
        while at <= end:
            row = [at.isoformat(), 100, 101, 99, 100, 50]
            if oi and not self.missing_oi:
                row.append(1000)
            rows.append(row)
            at += step
        if self.gap:
            rows = rows[1:]
        if self.conflict and self.calls == 2:
            rows[0][4] = 100.5
        return {"candles": rows}


class ExclusiveEndProvider(Provider):
    def historical_data(self, token, interval, start, end, *, oi=False):
        data = super().historical_data(token, interval, start, end, oi=oi)
        return {
            "candles": [
                r for r in data["candles"] if datetime.fromisoformat(r[0]) < end
            ]
        }


@pytest.mark.parametrize("oi", [False, True])
def test_complete_session_repeat_boundaries_and_csv_hash(tmp_path, oi):
    start = datetime(2026, 10, 30, 9, 15, tzinfo=IST)
    provider = Provider()
    path = tmp_path / "candles.csv"
    result = verify(
        provider,
        123,
        start,
        start + timedelta(minutes=15),
        "5minute",
        oi=oi,
        destination=path,
    )
    assert result["candles"] == 3
    assert result["completion_time_last"] == (start + timedelta(minutes=15)).isoformat()
    assert result["oi_present"] == (3 if oi else 0)
    assert result["overlapping_boundary_repeat_matches"]
    assert provider.calls == 2 and path.is_file()


@pytest.mark.parametrize("gap,conflict", [(True, False), (False, True)])
def test_gap_or_changed_boundary_prevents_success_export(tmp_path, gap, conflict):
    start = datetime(2026, 10, 30, 9, 15, tzinfo=IST)
    path = tmp_path / "candles.csv"
    with pytest.raises(ValueError):
        verify(
            Provider(gap, conflict),
            123,
            start,
            start + timedelta(minutes=15),
            "5minute",
            oi=False,
            destination=path,
        )
    assert not path.exists()


def test_missing_optional_oi_stays_missing(tmp_path):
    start = datetime(2026, 10, 30, 9, 15, tzinfo=IST)
    result = verify(
        Provider(missing_oi=True),
        123,
        start,
        start + timedelta(minutes=15),
        "5minute",
        oi=True,
        destination=tmp_path / "optional.csv",
    )
    assert result["oi_present"] == result["oi_positive"] == 0


@pytest.mark.parametrize("interval,expected", [("minute", 15), ("5minute", 3)])
def test_provider_exclusive_end_does_not_lose_last_completed_bar(
    tmp_path, interval, expected
):
    start = datetime(2026, 10, 30, 9, 15, tzinfo=IST)
    result = verify(
        ExclusiveEndProvider(),
        123,
        start,
        start + timedelta(minutes=15),
        interval,
        oi=True,
        destination=tmp_path / "exclusive.csv",
    )
    assert result["candles"] == expected
    assert result["completion_time_last"] == (start + timedelta(minutes=15)).isoformat()
