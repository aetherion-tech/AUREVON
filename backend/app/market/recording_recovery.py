"""Reconcile a quiescent recording tail against its committed event cursor."""

import json
from typing import TYPE_CHECKING
from uuid import UUID

from app.market.persistence import PersistenceError

if TYPE_CHECKING:
    from app.broker.kite_ticker import TickerWorker


def reconcile_recording(worker: "TickerWorker") -> int:
    """Validate the entire run before writes; commit each tail event and cursor.

    One offline writer only. Files must be frozen and retained. A crash during
    replay resumes after the last atomic checkpoint. Never re-record old events.
    """
    from app.tools.replay_ticks import replay_events, timestamp

    store, recorder, cursor = (
        worker.persistence,
        worker.recorder,
        worker.recording_cursor,
    )
    if store is None or recorder is None or cursor is None:
        raise PersistenceError(
            "Recording reconciliation requires retained recording files"
        )
    try:
        session, committed = cursor["session"], cursor["sequence"]
        if (
            not isinstance(session, str)
            or UUID(session).hex != session
            or type(committed) is not int
            or committed < 0
        ):
            raise ValueError("Invalid recording cursor")
        directory = recorder.directory.parent / session
        paths = sorted(directory.glob("*.jsonl"))
        # Existing deterministic replay validates sequences, seed, tokens and payloads
        # with bounded buffers. Do not write anything until the complete run passes.
        for _ in replay_events(paths):
            pass
        found = False
        for path in paths:
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    event = json.loads(line)
                    if (
                        event["session"] != session
                        or [event["spot_token"], event["future_token"]] != worker.tokens
                    ):
                        raise ValueError("Recording identity mismatch")
                    if (
                        event["kind"] == "checkpoint"
                        and event.get("configuration") != store.configuration
                    ):
                        raise ValueError("Recording configuration mismatch")
                    found = found or event["sequence"] == committed
        if not found:
            raise ValueError("Committed recording event is missing")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise PersistenceError(
            "Recording unavailable or invalid; retain files and rebuild"
        ) from None

    worker.recorder = None
    worker.persistence = None
    try:
        applied = 0
        for path in paths:
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    event = json.loads(line)
                    if event["sequence"] <= committed:
                        continue
                    worker.gap_required = event["gap"]
                    if "gaps" in event:
                        worker.gaps.restore(event["gaps"])
                    at = timestamp(event["at"])
                    if event["kind"] == "tick":
                        before = worker.accepted
                        worker._accept(
                            {
                                "instrument_token": event["token"],
                                "exchange_timestamp": timestamp(event["exchange_time"]),
                                "last_price": event["price"],
                                "volume_traded": event["volume"],
                                "oi": event["oi"],
                            },
                            at,
                        )
                        if worker.accepted != before + 1:
                            raise PersistenceError(
                                "Recording tail conflicts with checkpoint"
                            )
                    elif event["kind"] == "advance":
                        worker.advance_candles(at)
                    elif event["kind"] == "gap":
                        for builder in worker.candles.values():
                            builder.mark_gap()
                    worker.recording_cursor = {
                        "session": session,
                        "sequence": event["sequence"],
                    }
                    store.save(worker)
                    applied += 1
        return applied
    finally:
        worker.recorder = recorder
        worker.persistence = store
