"""Contract identity, point-in-time context, absent OI and atomic staging."""

import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as DBSession

from app.broker.kite_auth import IST, KiteAuth
from app.db.models import (
    Base,
    HistoricalContextBatch,
    HistoricalContextCandle,
    Instrument,
    MarketCheckpoint,
    StoredBrick,
    StoredCandle,
)
from app.db.session import database_engine
from app.market.context_history import fetch_context_history
from app.market.historical import parse_candle
from app.market.persistence import PersistenceError
from app.market.warmup import HistoryRange, Session, SessionCalendar, WarmupPlan


def ts(day, hour=9, minute=15):
    return datetime(2026, 10, day, hour, minute, tzinfo=IST)


def calendar():
    return SessionCalendar(
        date(2026, 10, 21),
        date(2026, 10, 24),
        tuple(Session(ts(d), ts(d, 15, 30)) for d in (21, 22, 23)),
    )


def plan(cutoff=None):
    return WarmupPlan(
        "cold_start",
        cutoff or ts(23, 9, 27),
        (HistoryRange("minute", ts(22), ts(22, 15, 29)),),
        (HistoryRange("5minute", ts(23), ts(23, 9, 20)),),
        date(2026, 10, 22),
    )


@pytest.fixture
def engine(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'context.db').as_posix()}")
    Base.metadata.create_all(engine)
    with DBSession(engine) as db, db.begin():
        for exchange, symbol, token, expiry, kind in (
            ("NSE", "NIFTY 50", 111, None, "EQ"),
            ("NFO", "NIFTYTESTFUT", 222, date(2026, 10, 29), "FUT"),
        ):
            db.add(
                Instrument(
                    exchange=exchange,
                    tradingsymbol=symbol,
                    instrument_token=token,
                    name="NIFTY",
                    expiry=expiry,
                    strike=0,
                    tick_size=0.05,
                    lot_size=65,
                    instrument_type=kind,
                    segment=exchange,
                )
            )
    yield engine
    engine.dispose()


def broker(*, oi=1000, omit_oi=False, missing_daily=None, fail_daily=False):
    auth = Mock(spec=KiteAuth)

    def historical(token, interval, start, end, **kwargs):
        if interval == "day":
            if fail_daily:
                raise ValueError("daily download failed")
            if start.day == missing_daily:
                return {"candles": []}
            price = 24000 + start.day
            return {
                "candles": [
                    [start.isoformat(), price, price + 2, price - 2, price + 1, 0]
                ]
            }
        step = timedelta(minutes=5 if interval == "5minute" else 1)
        rows = []
        cursor = start
        while cursor <= end:
            row = [
                cursor.isoformat(),
                "25000.125",
                "25002.125",
                "24998.125",
                "25001.125",
                500,
            ]
            if interval == "5minute" and not omit_oi:
                row.append(oi)
            rows.append(row)
            cursor += step
        return {"candles": rows}

    auth.historical_data.side_effect = historical
    return auth


def fetch(
    engine, auth=None, selected_plan=None, symbol="NIFTYTESTFUT", selected_calendar=None
):
    return fetch_context_history(
        auth or broker(),
        engine,
        "test",
        symbol,
        selected_plan or plan(),
        selected_calendar or calendar(),
    )


def counts(engine):
    with DBSession(engine) as db:
        return tuple(
            len(db.scalars(select(model)).all())
            for model in (
                HistoricalContextBatch,
                HistoricalContextCandle,
                MarketCheckpoint,
                StoredCandle,
                StoredBrick,
            )
        )


def metadata(engine, batch):
    with DBSession(engine) as db:
        return json.loads(db.get(HistoricalContextBatch, batch).provenance)


def test_contract_ohlc_volume_oi_and_point_in_time_daily_context(engine):
    auth = broker()
    result = fetch(engine, auth)
    assert (result.futures_received, result.futures_missing, result.oi_missing) == (
        2,
        0,
        0,
    )
    source = metadata(engine, result.batch_id)
    assert source["contract"]["tradingsymbol"] == "NIFTYTESTFUT"
    assert source["contract"]["expiry"] == "2026-10-29"
    assert source["contract"]["token"] == 222
    assert source["continuous"] is False
    current = source["daily_context"][-1]
    assert current["session"] == "2026-10-23"
    assert current["previous_close"] == "24023"
    assert current["previous_high"] == "24024"
    assert current["open"] == "25000.125"
    assert current["high"] == "25002.125"
    assert current["partial"] is True
    assert current["observed_through"] == str(ts(23, 9, 27))
    assert current["missing_minutes"] == 0
    with DBSession(engine) as db:
        candle = db.scalars(
            select(HistoricalContextCandle).where(
                HistoricalContextCandle.kind == "futures_5minute"
            )
        ).first()
        assert json.loads(candle.payload)["volume"] == "500"
        assert json.loads(candle.payload)["oi"] == "1000"
        assert "NIFTYTESTFUT:2026-10-29" in candle.identity
    assert counts(engine)[2:] == (0, 0, 0)
    assert not any(
        c.args[1] == "day" and c.args[2].day == 23
        for c in auth.historical_data.call_args_list
    )


@pytest.mark.parametrize(
    "oi,omit,missing", [(None, False, 2), (1000, True, 2), (0, False, 0)]
)
def test_absent_oi_is_null_and_zero_is_available(engine, oi, omit, missing):
    result = fetch(engine, broker(oi=oi, omit_oi=omit))
    assert result.oi_missing == missing
    with DBSession(engine) as db:
        row = db.scalars(
            select(HistoricalContextCandle).where(
                HistoricalContextCandle.kind == "futures_5minute"
            )
        ).first()
        assert json.loads(row.payload)["oi"] == (None if missing else "0")


def test_repeat_import_preserves_candles(engine):
    fetch(engine)
    before = counts(engine)
    fetch(engine)
    assert counts(engine) == (before[0] + 1, *before[1:])


def test_conflicting_oi_rejects_batch(engine):
    fetch(engine)
    before = counts(engine)
    with pytest.raises(PersistenceError, match="Conflicting"):
        fetch(engine, broker(oi=2000))
    assert counts(engine) == before


def test_missing_prior_daily_never_substitutes_older_close(engine):
    result = fetch(engine, broker(missing_daily=22))
    assert result.daily_missing == 1
    current = metadata(engine, result.batch_id)["daily_context"][-1]
    assert current["previous_close"] is None
    assert current["previous_session"] == "2026-10-22"


def test_end_of_day_uses_completed_daily_candle(engine):
    result = fetch(engine, selected_plan=plan(ts(23, 15, 30)))
    current = metadata(engine, result.batch_id)["daily_context"][-1]
    assert current["partial"] is False
    assert current["close"] == "24024"
    assert result.current_context_partial is False


def test_daily_failure_keeps_futures_uncommitted(engine):
    with pytest.raises(ValueError, match="daily download failed"):
        fetch(engine, broker(fail_daily=True))
    assert counts(engine) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("symbol", ["MISSING", "NIFTY 50"])
def test_wrong_contract_rejected_before_requests(engine, symbol):
    auth = broker()
    with pytest.raises(ValueError, match="Catalog"):
        fetch(engine, auth, symbol=symbol)
    auth.historical_data.assert_not_called()


def test_expired_contract_rejected_before_requests(engine):
    with DBSession(engine) as db, db.begin():
        db.get(Instrument, ("NFO", "NIFTYTESTFUT")).expiry = date(2026, 10, 22)
    auth = broker()
    with pytest.raises(ValueError, match="Expired"):
        fetch(engine, auth)
    auth.historical_data.assert_not_called()


@pytest.mark.parametrize("oi", [-1, "NaN", "broken"])
def test_invalid_oi_does_not_become_missing(engine, oi):
    with pytest.raises(ValueError, match="invalid historical candle"):
        fetch(engine, broker(oi=oi))
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_invalid_range_rejected_before_network(engine):
    auth = broker()
    invalid = replace(plan(), futures=(HistoryRange("5minute", ts(23), ts(23, 9, 25)),))
    with pytest.raises(ValueError, match="range"):
        fetch(engine, auth, selected_plan=invalid)
    auth.historical_data.assert_not_called()


def test_database_failure_rolls_back_batch_and_all_candles(engine):
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO historical_context_candles"):
            raise OperationalError("insert", {}, Exception("private detail"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(PersistenceError, match="previous data retained") as error:
            fetch(engine)
        assert "private detail" not in str(error.value)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_missing_oi_stays_strict_unless_requested():
    row = [ts(23).isoformat(), 1, 1, 1, 1, 0]
    with pytest.raises(ValueError):
        parse_candle(row, oi=True)
    assert parse_candle(row, oi=True, allow_missing_oi=True).oi is None


def test_missing_current_open_is_unknown_and_incomplete(engine):
    auth = broker()
    original = auth.historical_data.side_effect

    def missing_open(token, interval, start, end, **kwargs):
        response = original(token, interval, start, end, **kwargs)
        if interval == "minute":
            response["candles"] = response["candles"][1:]
        return response

    auth.historical_data.side_effect = missing_open
    result = fetch(engine, auth)
    current = metadata(engine, result.batch_id)["daily_context"][-1]
    assert current["open"] is None
    assert current["missing_minutes"] == 1
    assert current["partial"] is True
    assert current["observed_through"] == str(ts(23, 9, 27))


def test_unexpected_daily_date_rejects_entire_import(engine):
    auth = broker()
    original = auth.historical_data.side_effect

    def wrong_day(token, interval, start, end, **kwargs):
        response = original(token, interval, start, end, **kwargs)
        if interval == "day":
            response["candles"][0][0] = ts(20).isoformat()
        return response

    auth.historical_data.side_effect = wrong_day
    with pytest.raises(ValueError, match="outside requested session"):
        fetch(engine, auth)
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_no_futures_response_is_explicitly_missing(engine):
    auth = broker()
    original = auth.historical_data.side_effect

    def no_futures(token, interval, start, end, **kwargs):
        if interval == "5minute":
            return {"candles": []}
        return original(token, interval, start, end, **kwargs)

    auth.historical_data.side_effect = no_futures
    result = fetch(engine, auth)
    assert result.futures_missing == 2
    assert result.futures_received == 0
    assert result.oi_missing == 0
    assert metadata(engine, result.batch_id)["futures_expected"] == 2


def test_special_session_daily_completion_uses_calendar(engine):
    special = SessionCalendar(
        date(2026, 10, 21),
        date(2026, 10, 24),
        (
            Session(ts(21), ts(21, 15, 30)),
            Session(ts(22), ts(22, 15, 30)),
            Session(ts(23), ts(23, 10, 0)),
        ),
    )
    result = fetch(engine, selected_plan=plan(ts(23, 10, 0)), selected_calendar=special)
    current = metadata(engine, result.batch_id)["daily_context"][-1]
    assert current["partial"] is False
    assert current["observed_through"] == str(ts(23, 10, 0))


def test_preopen_context_has_previous_close_without_inventing_today(engine):
    preopen = replace(plan(ts(23, 8, 0)), futures=())
    result = fetch(engine, selected_plan=preopen)
    contexts = metadata(engine, result.batch_id)["daily_context"]
    assert contexts[-1]["session"] == "2026-10-22"
    assert contexts[-1]["close"] == "24023"
    assert not any(context["session"] == "2026-10-23" for context in contexts)
