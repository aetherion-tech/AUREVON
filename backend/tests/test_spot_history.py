"""Exercise the downloader and SQLite transactions with fake broker data."""

import json
from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.broker.kite_auth import KiteAuth
from app.db.models import (
    Base,
    HistoricalSpotBatch,
    HistoricalSpotCandle,
    Instrument,
    MarketCheckpoint,
    StoredBrick,
    StoredCandle,
)
from app.db.session import database_engine
from app.market.persistence import PersistenceError
from app.market.spot_history import fetch_spot_history
from app.market.warmup import HistoryRange, WarmupPlan

START = datetime.fromisoformat("2026-10-23T09:15:00+05:30")


@pytest.fixture
def engine(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'history.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        db.add(
            Instrument(
                exchange="NSE",
                tradingsymbol="NIFTY 50",
                instrument_token=111,
                name="NIFTY",
                expiry=None,
                strike=0,
                tick_size=0.05,
                lot_size=0,
                instrument_type="EQ",
                segment="INDICES",
            )
        )
    yield engine
    engine.dispose()


def plan(*ranges):
    return WarmupPlan(
        "cold_start",
        START + timedelta(minutes=3),
        ranges or (HistoryRange("minute", START, START + timedelta(minutes=2)),),
        (),
        date(2026, 10, 22),
    )


def row(minute=0, close="24000.125"):
    return [
        (START + timedelta(minutes=minute)).isoformat(),
        close,
        close,
        close,
        close,
        0,
    ]


def broker(rows):
    auth = Mock(spec=KiteAuth)
    auth.historical_data.return_value = {"candles": rows}
    return auth


def counts(engine):
    with Session(engine) as db:
        return tuple(
            len(db.scalars(select(model)).all())
            for model in (
                HistoricalSpotBatch,
                HistoricalSpotCandle,
                MarketCheckpoint,
                StoredCandle,
                StoredBrick,
            )
        )


def test_exact_storage_provenance_and_repeat_import(engine):
    auth = broker([row(0), row(1), row(2)])
    result = fetch_spot_history(auth, engine, "test", 111, plan())
    assert (result.received, result.inserted, result.missing_minutes) == (3, 3, 0)
    auth.historical_data.assert_called_once_with(
        111, "minute", START, START + timedelta(minutes=2), oi=False
    )
    with Session(engine) as db:
        saved = db.scalars(
            select(HistoricalSpotCandle).order_by(HistoricalSpotCandle.time)
        ).all()
        assert saved[0].time == START.astimezone(UTC).isoformat()
        assert (
            saved[0].completed_at
            == (START + timedelta(minutes=1)).astimezone(UTC).isoformat()
        )
        assert json.loads(saved[0].payload)["close"] == "24000.125"
        batch = db.get(HistoricalSpotBatch, result.batch_id)
        source = json.loads(batch.provenance)
        assert source["source"] == "kite_historical"
        assert source["tradingsymbol"] == "NIFTY 50"
        assert source["received_minutes"] == source["expected_minutes"] == 3
        assert datetime.fromisoformat(source["fetched_at"]).tzinfo is not None
        assert len(source["ranges"]) == 1
    auth.historical_data.return_value = {
        "candles": [row(i, "24000.1250") for i in range(3)]
    }
    repeat = fetch_spot_history(auth, engine, "test", 111, plan())
    assert repeat.inserted == 0
    assert counts(engine) == (2, 3, 0, 0, 0)


@pytest.mark.parametrize("rows,missing", [([], 3), ([row(0), row(2)], 1)])
def test_empty_and_partial_responses_are_recorded_without_fabrication(
    engine, rows, missing
):
    result = fetch_spot_history(broker(rows), engine, "test", 111, plan())
    assert result.missing_minutes == missing
    assert counts(engine) == (1, 3 - missing, 0, 0, 0)


def test_conflict_rolls_back_batch_and_earlier_new_rows(engine):
    fetch_spot_history(broker([row(2)]), engine, "test", 111, plan())
    with pytest.raises(PersistenceError, match="Conflicting"):
        fetch_spot_history(
            broker([row(0), row(2, "25000")]), engine, "test", 111, plan()
        )
    assert counts(engine) == (1, 1, 0, 0, 0)


def test_later_download_failure_leaves_no_partial_import(engine):
    auth = broker([])
    auth.historical_data.side_effect = [{"candles": [row(0)]}, ValueError("failed")]
    ranges = (
        HistoryRange("minute", START, START),
        HistoryRange(
            "minute", START + timedelta(minutes=2), START + timedelta(minutes=2)
        ),
    )
    with pytest.raises(ValueError, match="failed"):
        fetch_spot_history(auth, engine, "test", 111, plan(*ranges))
    assert counts(engine) == (0, 0, 0, 0, 0)


def test_database_failure_rolls_back_batch(engine):
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO historical_spot_candles"):
            raise OperationalError("insert", {}, Exception("private database detail"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(PersistenceError, match="previous data retained") as error:
            fetch_spot_history(broker([row()]), engine, "test", 111, plan())
        assert "private" not in str(error.value)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert counts(engine) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    "rows",
    [
        [row(4)],
        [row(0), row(0, "25000")],
        [[START.replace(second=1).isoformat(), 1, 1, 1, 1, 0]],
    ],
)
def test_bad_broker_data_preserves_storage(engine, rows):
    with pytest.raises(ValueError):
        fetch_spot_history(broker(rows), engine, "test", 111, plan())
    assert counts(engine) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    "ranges",
    [
        (HistoryRange("5minute", START, START),),
        (HistoryRange("minute", START, START + timedelta(minutes=3)),),
        (HistoryRange("minute", START, START), HistoryRange("minute", START, START)),
    ],
)
def test_invalid_plan_rejected_before_network(engine, ranges):
    auth = broker([])
    with pytest.raises(ValueError):
        fetch_spot_history(auth, engine, "test", 111, plan(*ranges))
    auth.historical_data.assert_not_called()


def test_wrong_catalog_token_rejected_before_network(engine):
    auth = broker([])
    with pytest.raises(ValueError, match="catalog"):
        fetch_spot_history(auth, engine, "test", 222, plan())
    auth.historical_data.assert_not_called()
    assert counts(engine) == (0, 0, 0, 0, 0)
