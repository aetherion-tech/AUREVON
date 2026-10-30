"""Real recovery/admission paths with isolated providers, never G1/G3/G5 proof."""

import asyncio
import json
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_domain_api import post, prepared

from app.db.models import MarketCheckpoint

pytest_plugins = ["test_domain_api", "test_market_service"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault,fail_history",
    [
        ("disconnect", False),
        ("overflow", False),
        ("token_expiry", False),
        ("disconnect", True),
    ],
)
async def test_recovery_faults_deny_new_admissions_through_validated_handoff(
    managed, domain, fault, fail_history
):
    market, wall, auth, workers, _ = managed
    elapsed = [0.0]
    factory = market.worker_factory

    def bounded_factory(*args, **kwargs):
        kwargs["capacity"] = 2
        worker = factory(*args, **kwargs)
        worker.resume_gate.clock = lambda: elapsed[0]
        return worker

    market.worker_factory = bounded_factory
    original_gate = domain["runtime"].readiness
    initial = domain["wallet"].snapshot()
    decision = [None]
    key = f"{fault}-{fail_history}-stable-confirm"

    def gate(at):
        current = market.worker
        authenticated = auth.managed_session() is not None
        state = current.status() if current is not None else {}
        return original_gate(at).model_copy(
            update={
                "authenticated": authenticated,
                "feed": bool(current and state["connected"] and not state["stale"]),
                "clock": bool(current and not state["clock_or_feed_delay"]),
                "recovered": bool(
                    current
                    and current.entry_eligible(
                        authenticated=authenticated,
                        session_eligible=True,
                        indicators_ready=True,
                    )
                ),
            }
        )

    def denied(phase):
        assert not gate(domain["wall"][0]).ready(), phase
        if decision[0] is None:
            decision[0] = prepared(domain, key=f"{fault}-{fail_history}-stable-prepare")
        identity = decision[0]
        result = post(
            domain,
            f"/api/decisions/{identity}/confirm",
            key=key,
        )
        assert result.status_code == 200 and not result.json()["accepted"], result.text
        assert "readiness" in result.json()["reason"]
        book = domain["wallet"].snapshot()
        assert not book.positions and book.reserved == 0
        assert book.balance == initial.balance and book.ledger == initial.ledger
        assert not domain["service"].entries_enabled()
        return identity, result.json()

    try:
        await market.start()
        first = market.worker
        assert first is not None, market.status()
        assert first.resume_gate.started is not None
        domain["runtime"].readiness = gate
        # Full production eligibility is already correctly blocked by unfinished
        # live-volume provenance; never clear those flags to manufacture a pass.
        assert not first._entry_source_quality()

        if fault == "disconnect":
            first.socket.on_close(first.socket, 1006, "private-provider-error")
            await asyncio.sleep(0)
            assert not first.connected and first.gap_required
        elif fault == "overflow":
            first._enqueue(
                [
                    dict(
                        instrument_token=111,
                        exchange_timestamp=wall[0],
                        last_price=150 + i,
                        volume_traded=100,
                        oi=50,
                    )
                    for i in range(3)
                ],
                wall[0],
            )
            assert first.dropped == 1 and first.gap_required
            assert any(g["reason"] == "overflow" for g in first.gaps.snapshot())
        else:
            auth.managed_session.return_value = None
            await market.step()
            assert market.worker is None and market.reason == "login_required"
            assert not first.running
        rejected_id, rejected = denied("fault")

        # Reconnection/auth restoration alone cannot release final admission.
        if fault == "disconnect":
            first.socket.on_connect(first.socket, {})
            await asyncio.sleep(0)
            assert first.connected and first.gap_required
        elif fault == "token_expiry":
            auth.managed_session.return_value = (
                "replacement-generation",
                wall[0] + timedelta(hours=2),
            )
            assert market.worker is None
        denied("transport-restored-only")

        if fail_history:
            auth.historical_data.side_effect = RuntimeError("private-provider-error")
        wall[0] += timedelta(minutes=5)
        await market.step()
        assert not first.running and first.task.done()
        if fail_history:
            assert market.worker is None
            assert market.reason == "market_start_or_recovery_failed"
            assert "private-provider-error" not in str(market.status())
            denied("failed-recovery")
            return

        recovered = market.worker
        assert recovered is not None and recovered is not first, market.status()
        assert len(workers) == 2
        assert not recovered.gap_required
        assert recovered.resume_gate.started is not None
        assert not recovered.resume_gate.eligible(healthy=recovered._resume_health())
        denied("entry-delay")
        elapsed[0] = 60.0
        # Full source quality remains a mandatory gate and revokes the hold;
        # elapsed time cannot restore validation that source quality revoked.
        assert not recovered._entry_source_quality()
        denied("source-still-partial")

        with Session(market.engine) as db:
            checkpoint = db.scalars(select(MarketCheckpoint)).first()
            state = json.loads(checkpoint.state)
        assert state["validated_recovery"]["unfinished_live_bucket_partial"] is True
        assert state["validated_recovery"]["retired_gaps"]
        retry = post(
            domain,
            f"/api/decisions/{rejected_id}/confirm",
            key=key,
        )
        assert retry.json() == rejected
    finally:
        domain["runtime"].readiness = original_gate
        await market.close()
