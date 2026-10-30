"""Integrated operator-control drills on a temporary synthetic paper account.

These are engineering drill evidence, never actual exchange sessions or G5.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from test_domain_api import admitted, post, prepared

from app.broker.kite_ticker import TickerWorker
from app.execution.models import PositionStatus
from app.wallet.reconciliation import WalletReconciler
from app.wallet.service import WalletService

pytest_plugins = ["test_domain_api"]


@pytest.mark.parametrize("control", ["manual", "kill", "daily_loss", "square_off"])
def test_control_waits_for_quotes_then_closes_and_reconciles(domain, control):
    _, identity = admitted(domain)
    service, wallet, runtime = domain["service"], domain["wallet"], domain["runtime"]
    initial = wallet.snapshot()
    original_prices = runtime.prices

    def adverse_prices():
        prices = original_prices()
        token = initial.positions[identity].plan.short.contract.token
        old = prices[token]
        prices[token] = old.model_copy(
            update={
                "last": old.last + 50,
                "bid": old.bid + 50,
                "ask": old.ask + 50,
            }
        )
        return prices

    if control == "daily_loss":
        runtime.prices = adverse_prices
        service.poll(domain["wall"][0])
        assert wallet.snapshot().loss_locked
        fresh_prices = adverse_prices
    else:
        fresh_prices = original_prices
    runtime.prices = lambda: {}
    if control in ("manual", "kill"):
        path = f"/api/trades/{identity}/close" if control == "manual" else "/api/kill"
        response = post(domain, path, key="drill-control")
        assert response.status_code == 200, response.text
        assert post(domain, path, key="drill-control").json() == response.json()
    if control == "square_off":
        domain["wall"][0] = domain["wall"][0].replace(hour=15, minute=30)
    for _ in range(3):
        service.poll(domain["wall"][0])
    waiting = wallet.snapshot()
    assert waiting.positions[identity].status == PositionStatus.CLOSING
    assert waiting.reserved == initial.reserved > 0
    assert (
        sum(o.fill is not None for o in waiting.positions[identity].orders.values())
        == 2
    )
    assert not service.entries_enabled()
    assert domain["client"].get(f"/api/trades/{identity}").json()["state"] == "CLOSING"

    # Control exits continue even when new-entry readiness fails completely.
    original_gate = runtime.readiness
    runtime.readiness = lambda at: original_gate(at).model_copy(update={"feed": False})
    runtime.prices = fresh_prices
    for _ in range(8):
        service.poll(domain["wall"][0])
    final = wallet.snapshot()
    position = final.positions[identity]
    assert position.status == PositionStatus.CLOSED
    assert position.exit_reason == control
    assert final.reserved == 0
    assert sum(o.fill is not None for o in position.orders.values()) == 4
    assert len({entry.key for entry in final.ledger}) == len(final.ledger)
    assert final.balance == Decimal(100000) + position.gross - position.costs
    client = domain["client"]
    assert client.get("/api/positions/open").json() == []
    detail = client.get(f"/api/trades/{identity}").json()
    assert Decimal(detail["net"]) == position.gross - position.costs
    assert client.get("/api/pnl/summary?period=all").json()["net"] == detail["net"]
    assert Decimal(client.get("/api/wallet").json()["balance"]) == final.balance
    assert set(
        WalletReconciler(wallet.engine).poll(domain["wall"][0], force=True).values()
    ) == {"PASS"}

    restored = WalletService(
        wallet.engine,
        wallet.calendar,
        wallet.fills,
        wallet.risk,
        settings=final.wallet_settings,
    ).snapshot()
    assert restored == final
    assert restored.killed == (control == "kill")
    assert restored.loss_locked == (control == "daily_loss")
    before = wallet.snapshot()
    for _ in range(3):
        service.poll(domain["wall"][0])
    assert wallet.snapshot().positions == before.positions
    assert wallet.snapshot().ledger == before.ledger


def test_clock_drift_warns_rejects_and_preserves_rejected_decision_after_recovery(
    domain,
):
    identity = prepared(domain)
    market, runtime = domain["app"].state.market_service, domain["runtime"]
    worker = TickerWorker(None, 111, 222, clock=lambda: domain["wall"][0])
    market.worker = worker
    original = runtime.readiness
    runtime.readiness = lambda at: original(at).model_copy(
        update={"clock": not worker.status()["clock_or_feed_delay"]}
    )
    assert domain["service"].entries_enabled()
    now = domain["wall"][0]
    for token in (111, 222):
        worker._accept(
            dict(
                instrument_token=token,
                exchange_timestamp=now - timedelta(seconds=3),
                last_price=24000,
                volume_traded=100,
                oi=50,
            ),
            now,
        )
    assert worker.status()["clock_or_feed_delay"]
    assert not worker.status()["stale"]
    domain["app"].state.live_service.sample()
    assert any(
        a["code"] == "clock_or_feed_delay"
        for a in domain["client"].get("/api/alerts").json()["items"]
    )
    assert not domain["service"].entries_enabled()
    path = f"/api/decisions/{identity}/confirm"
    response = post(domain, path, key="clock-reject")
    assert response.status_code == 200 and not response.json()["accepted"]
    assert not domain["wallet"].snapshot().positions
    for token in (111, 222):
        worker._accept(
            dict(
                instrument_token=token,
                exchange_timestamp=now,
                last_price=24000,
                volume_traded=100,
                oi=50,
            ),
            now,
        )
    assert not worker.status()["clock_or_feed_delay"]
    assert domain["service"].entries_enabled()
    assert post(domain, path, key="clock-reject").json() == response.json()
    assert not domain["wallet"].snapshot().positions
    market.worker = None
