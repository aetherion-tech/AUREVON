"""Managed socket lifecycle without a real connection or account."""

import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from test_option_planner import NOW, catalog

from app.broker.kite_ticker import TickerWorker
from app.market.tick_recording import TickRecorder
from app.strategy.quotes import OptionQuoteBook


def tick(c, **kw):
    return {
        "instrument_token": c.token,
        "exchange_timestamp": NOW,
        "last_price": 10,
        "oi": 100,
        "depth": {
            "buy": [{"price": 10, "quantity": 100, "orders": 1}],
            "sell": [{"price": 10.5, "quantity": 100, "orders": 1}],
        },
    } | kw


def test_normalized_depth_and_invalid_update_removes_old_quote():
    c = catalog().contracts[0]
    book = OptionQuoteBook()
    book.configure([c])
    assert book.accept(tick(c), NOW)
    assert book.snapshot()[c.token].bids[0].price == Decimal("10")
    assert not book.accept(tick(c, depth={}), NOW)
    assert not book.snapshot()
    assert book.invalid == 1


@pytest.mark.parametrize(
    "change",
    [
        {"oi": None},
        {"oi": -1},
        {"exchange_timestamp": NOW + timedelta(seconds=1)},
        {
            "depth": {
                "buy": [{"price": 11, "quantity": 1}],
                "sell": [{"price": 10, "quantity": 1}],
            }
        },
        {"depth": {"buy": [], "sell": []}},
        {"exchange_timestamp": "bad"},
    ],
)
def test_missing_crossed_future_or_invalid_depth_is_rejected(change):
    c = catalog().contracts[0]
    book = OptionQuoteBook()
    book.configure([c])
    assert not book.accept(tick(c, **change), NOW)
    assert not book.snapshot()


def test_pinned_traded_contract_capacity_identity_and_out_of_order():
    a, b, c = catalog().contracts[:3]
    book = OptionQuoteBook(capacity=2)
    book.configure([a], [b])
    assert set(book.tokens) == {a.token, b.token}
    book.accept(tick(b), NOW)
    book.configure([c])
    assert set(book.tokens) == {b.token, c.token}
    assert book.snapshot()[b.token].contract == b
    with pytest.raises(ValueError, match="capacity"):
        book.configure([a, c])
    with pytest.raises(ValueError, match="identity"):
        book.configure([b.model_copy(update={"symbol": "CHANGED"})])
    assert not book.accept(tick(b, exchange_timestamp=NOW - timedelta(seconds=1)), NOW)
    assert not book.snapshot()


@pytest.mark.asyncio
async def test_worker_subscribe_unsubscribe_pin_reconnect_and_core_isolation():
    a, b, c = catalog().contracts[:3]
    socket = Mock()
    worker = TickerWorker(socket, 111, 222, clock=lambda: NOW)
    worker.running = worker.connected = True
    with patch(
        "twisted.internet.reactor.callFromThread", side_effect=lambda f, *a: f(*a)
    ):
        await worker.set_option_contracts([a], [b])
        socket.subscribe.assert_called_with([a.token, b.token])
        socket.set_mode.assert_called_with(socket.MODE_FULL, [a.token, b.token])
        worker._accept(tick(a), NOW)
        assert a.token in worker.option_quotes.snapshot()
        assert worker.accepted == 0 and worker.tokens == [111, 222]
        await worker.set_option_contracts([c])
        socket.unsubscribe.assert_called_with([a.token])
        assert b.token in worker.option_quotes.tokens
        worker._disconnected()
        assert not worker.option_quotes.snapshot()
        worker._on_connect(socket, {})
        socket.subscribe.assert_called_with([111, 222, b.token, c.token])
        assert set(worker.candles) == {111, 222}


@pytest.mark.asyncio
async def test_subscription_error_fails_closed_and_same_desired_set_can_retry():
    c = catalog().contracts[0]
    socket = Mock()
    worker = TickerWorker(socket, 111, 222)
    worker.running = worker.connected = True
    with patch(
        "twisted.internet.reactor.callFromThread", side_effect=lambda f, *a: f(*a)
    ):
        socket.subscribe.side_effect = RuntimeError("fake failure")
        with pytest.raises(RuntimeError, match="subscription"):
            await worker.set_option_contracts([c])
        assert (
            not worker.option_quotes.snapshot()
            and worker.option_quotes.subscription_error
        )
        socket.subscribe.side_effect = None
        await worker.set_option_contracts([c])
        assert not worker.option_quotes.subscription_error
        assert socket.subscribe.call_count == 2


def test_full_depth_recording_is_separate_from_core_run(tmp_path):
    c = catalog().contracts[0]
    recorder = TickRecorder(tmp_path, 111, 222)
    worker = TickerWorker(None, 111, 222, recorder=recorder)
    worker.option_quotes.configure([c])
    worker._accept(tick(c), NOW)
    worker._accept(tick(c), NOW)
    assert recorder.sequence == 0 and recorder.option_sequence == 2
    assert not list(recorder.directory.glob("*.jsonl"))
    rows = [
        json.loads(line)
        for line in next((recorder.directory / "options").glob("*.jsonl"))
        .read_text()
        .splitlines()
    ]
    assert [r["sequence"] for r in rows] == [0, 1]
    assert rows[0]["quote"]["contract"]["symbol"] == c.symbol
    assert rows[0]["quote"]["asks"][0]["price"] == "10.5"


def test_gap_invalidates_option_quotes():
    c = catalog().contracts[0]
    worker = TickerWorker(None, 111, 222)
    worker.option_quotes.configure([c])
    worker._accept(tick(c), NOW)
    worker._track_gap("overflow", NOW)
    assert not worker.option_quotes.snapshot()
