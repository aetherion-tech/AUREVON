"""Offline missing-bar recovery with atomic derived-state replacement."""

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import uuid4

from sqlalchemy import CursorResult, Engine, delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.broker.kite_auth import AuthError, KiteAuth
from app.broker.request_limits import RecoveryBusyError, single_recovery
from app.config import Settings
from app.db.models import (
    HistoricalContextBatch,
    HistoricalContextCandle,
    HistoricalSpotBatch,
    HistoricalSpotCandle,
    Instrument,
    MarketCheckpoint,
    StoredBrick,
    StoredCandle,
)
from app.market.candles_5m import CandleBuilder, MarketCandle
from app.market.gaps import GapTracker
from app.market.historical import Candle, download, parse_candle
from app.market.persistence import (
    MarketPersistence,
    PersistenceError,
    builder_state,
    candle_from,
    encode,
    restore_builder,
)
from app.market.recovery_progress import RecoveryProgress
from app.market.recovery_requests import RecoveryHistoryClient, RecoveryRequestError
from app.market.renko_builder import Brick
from app.market.warmup import HistoryRange, SessionCalendar, local_time


@dataclass(frozen=True)
class RecoveryResult:
    revision: int
    imported: bool
    spot_inserted: int
    futures_inserted: int
    spot_missing: int
    futures_missing: int
    retained_partial: int
    oi_missing: int
    spot_corrected: int = 0
    futures_corrected: int = 0
    request_retries: int = 0
    entries_enabled: Literal[False] = False


def _missing_ranges(
    ranges: tuple[HistoryRange, ...],
    existing: dict[datetime, MarketCandle],
) -> tuple[HistoryRange, ...]:
    out: list[HistoryRange] = []
    for item in ranges:
        step = timedelta(minutes=1 if item.interval == "minute" else 5)
        at = item.start
        while at <= item.end:
            if at not in existing:
                if out and out[-1].end + step == at:
                    out[-1] = replace(out[-1], end=at)
                else:
                    out.append(HistoryRange(item.interval, at, at))
            at += step
    return tuple(out)


@single_recovery
def recover_missing_history(
    auth: KiteAuth,
    engine: Engine,
    settings: Settings,
    stream: str,
    spot_token: int,
    future_token: int,
    futures_identity: str,
    calendar: SessionCalendar,
    cutoff: datetime,
    *,
    correct_partial: bool = False,
    progress: RecoveryProgress | None = None,
) -> RecoveryResult:
    monitor = progress if progress is not None else RecoveryProgress()
    monitor.begin()
    try:
        return _recover_missing_history(
            auth,
            engine,
            settings,
            stream,
            spot_token,
            future_token,
            futures_identity,
            calendar,
            cutoff,
            correct_partial=correct_partial,
            progress=monitor,
        )
    except AuthError as error:
        monitor.failed(
            "authentication_required"
            if error.status_code == 401
            else "source_unavailable"
        )
        raise
    except RecoveryBusyError:
        monitor.failed("recovery_busy")
        raise
    except RecoveryRequestError:
        monitor.failed("source_unavailable")
        raise
    except PersistenceError:
        monitor.failed("persistence_failed")
        raise
    except (ValueError, TypeError, KeyError):
        monitor.failed("invalid_scope")
        raise
    except BaseException:
        monitor.failed("unexpected_failure")
        raise


def _recover_missing_history(
    auth: KiteAuth,
    engine: Engine,
    settings: Settings,
    stream: str,
    spot_token: int,
    future_token: int,
    futures_identity: str,
    calendar: SessionCalendar,
    cutoff: datetime,
    *,
    correct_partial: bool = False,
    progress: RecoveryProgress,
) -> RecoveryResult:
    """Recover a quiescent stream, then restore a NEW worker from its checkpoint.

    Stop the stream's writer before calling. No live worker is mutated. Revision
    checks reject concurrent writers. Missing bars are fetched by default; explicit
    correct_partial also replaces completed partial bars from historical sources.
    Complete bars and unfinished active bars are never correction candidates. Downloads
    finish before one transaction stages sources and replaces derived outputs.
    Entries and unresolved-gap flags remain disabled/preserved even on success.
    """
    finish = local_time(cutoff)
    if settings.renko_mode != "minute_close" or settings.renko_anchor is None:
        raise ValueError("Recovery requires minute_close mode and an explicit anchor")
    if min(spot_token, future_token) <= 0 or spot_token == future_token:
        raise ValueError("Expected distinct positive spot/futures tokens")
    store = MarketPersistence(
        engine,
        stream,
        spot_token,
        future_token,
        box=settings.renko_box,
        anchor=settings.renko_anchor,
    )
    tokens = [spot_token, future_token]
    try:
        with Session(engine) as db, db.begin():
            checkpoint = db.get(MarketCheckpoint, stream)
            if checkpoint is None or checkpoint.configuration != store.configuration:
                raise PersistenceError("Recovery requires a matching stream checkpoint")
            revision, old_state = checkpoint.revision, checkpoint.state
            state = json.loads(old_state)
            if state["version"] != 1:
                raise ValueError("Unknown checkpoint version")
            spot = db.get(Instrument, ("NSE", "NIFTY 50"))
            futures = db.scalars(
                select(Instrument).where(
                    Instrument.exchange == "NFO",
                    Instrument.name == "NIFTY",
                    Instrument.instrument_type == "FUT",
                    Instrument.instrument_token == future_token,
                )
            ).all()
            if (
                spot is None
                or spot.instrument_token != spot_token
                or len(futures) != 1
                or futures[0].expiry is None
                or futures[0].expiry < finish.date()
                or futures_identity
                != (f"NFO:{futures[0].tradingsymbol}:{futures[0].expiry.isoformat()}")
            ):
                raise ValueError(
                    "Recovery tokens must match the exact catalog identity"
                )
            for key in ("historical_import", "recovery"):
                identity = state.get(key, {}).get("futures_identity", futures_identity)
                if identity != futures_identity:
                    raise ValueError(
                        "Futures identity changed; explicit rollover required"
                    )
            rows = db.scalars(
                select(StoredCandle)
                .where(StoredCandle.stream == stream)
                .order_by(StoredCandle.time)
            ).all()
            original = {(r.token, r.time): r.payload for r in rows}
            original_bricks = {
                r.index: r.payload
                for r in db.scalars(
                    select(StoredBrick).where(StoredBrick.stream == stream)
                )
            }
            candles: dict[int, dict[datetime, MarketCandle]] = {t: {} for t in tokens}
            for row in rows:
                candle = candle_from(json.loads(row.payload))
                if (
                    row.token not in tokens
                    or row.time != (candle.time.astimezone(UTC).isoformat())
                    or candle.end > finish
                ):
                    raise ValueError("Stored candles exceed recovery scope/cutoff")
                candles[row.token][candle.time] = candle
    except SQLAlchemyError:
        raise PersistenceError(
            "Recovery database unavailable; previous data retained"
        ) from None

    tracker = GapTracker(tokens)
    tracker.restore(state.get("gaps", []))
    old_builders: dict[int, CandleBuilder] = {}
    for token, minutes in ((spot_token, 1), (future_token, 5)):
        builder = CandleBuilder(minutes, futures=token == future_token)
        restore_builder(builder, state["builders"][str(token)])
        old_builders[token] = builder
        if (
            builder.current is not None
            and candles[token]
            and builder.current.time < max(c.end for c in candles[token].values())
        ):
            raise ValueError("Active candle overlaps completed stored history")
        boundary = (
            builder.current.time
            if builder.current is not None
            else builder._closed_until or builder.last_time
        )
        if boundary is None:
            # An uninitialized side needs a supplied gap origin; guessing a
            # lookback would change the stream's source coverage silently.
            starts = [g["start"] for g in tracker.snapshot() if g["token"] == token]
            origin_plan = state.get("historical_import", {}).get("plan", {})
            starts.extend(
                local_time(datetime.fromisoformat(r["start"]))
                for r in origin_plan.get(
                    "spot" if token == spot_token else "futures", []
                )
            )
            if not starts:
                raise ValueError("Recovery lacks an instrument source boundary")
            boundary = min(starts)
        if boundary > finish or (
            builder.last_time is not None and builder.last_time > finish
        ):
            raise ValueError("Recovery cutoff precedes checkpoint state")
        if state["counts"][str(token)] != len(candles[token]):
            raise PersistenceError("Checkpoint/source candle count mismatch")
        tracker.mark(token, "downtime", boundary, resume_after=finish)
    earliest = min(g["start"] for g in tracker.snapshot())
    if finish - earliest > timedelta(days=settings.recovery_max_gap_days):
        raise ValueError("Gap exceeds automatic recovery limit")
    ranges = {
        spot_token: tracker.ranges(spot_token, 1, calendar, finish),
        future_token: tracker.ranges(future_token, 5, calendar, finish),
    }
    # Also find interior holes in retained history (including gaps recorded by
    # old checkpoints without explicit spans). Replaying every retained source
    # preserves the original grid seed and session VWAP context.
    for token, minutes in ((spot_token, 1), (future_token, 5)):
        starts = [*candles[token], *(r.start for r in ranges[token])]
        origin_plan = state.get("historical_import", {}).get("plan", {})
        for r in origin_plan.get("spot" if token == spot_token else "futures", []):
            starts.append(local_time(datetime.fromisoformat(r["start"])))
        if not starts:
            continue
        start = min(starts)
        if start.date() < calendar.first_date:
            raise ValueError("Calendar must cover the full retained source history")
        coverage: list[HistoryRange] = []
        step = timedelta(minutes=minutes)
        for session in calendar.sessions:
            opening = local_time(session.opening)
            first = max(opening, opening + ((start - opening) // step) * step)
            end = (
                opening
                + ((min(local_time(session.closing), finish) - opening) // step - 1)
                * step
            )
            if first <= end:
                coverage.append(
                    HistoryRange("minute" if minutes == 1 else "5minute", first, end)
                )
        ranges[token] = tuple(coverage)
    requested = {
        t: _missing_ranges(
            ranges[t],
            {
                stamp: c
                for stamp, c in candles[t].items()
                if not (correct_partial and c.partial)
            },
        )
        for t in tokens
    }
    if any(
        finish - r.start > timedelta(days=settings.recovery_max_gap_days)
        for items in requested.values()
        for r in items
    ):
        raise ValueError("Missing source exceeds automatic recovery limit")
    fetched: dict[int, list[Candle]] = {t: [] for t in tokens}
    corrections: dict[tuple[int, str], dict[str, Any]] = {}
    client = RecoveryHistoryClient(auth, settings)
    total_ranges = sum(len(items) for items in requested.values())
    completed_ranges = 0
    progress.stage("downloading", total=total_ranges)
    for token in tokens:
        for item in requested[token]:
            for source in download(
                client,
                token,
                item.start,
                item.end,
                interval=item.interval,
                oi=token == future_token,
                allow_missing_oi=True,
                now=finish,
            ):
                step = timedelta(minutes=1 if token == spot_token else 5)
                if (source.time - item.start) % step != timedelta(0):
                    raise ValueError("Recovery source is not candle-aligned")
                fetched[token].append(source)
                old_candle = candles[token].get(source.time)
                recovered = MarketCandle(
                    source.time,
                    source.time + step,
                    source.open,
                    source.high,
                    source.low,
                    source.close,
                    source.volume if token == future_token else None,
                    source.oi if token == future_token else None,
                    False,
                )
                if old_candle is not None:
                    if not correct_partial or not old_candle.partial:
                        raise ValueError(
                            "Only completed partial candles may be corrected"
                        )
                    corrections[token, source.time.astimezone(UTC).isoformat()] = {
                        "reason": "completed_partial_replaced",
                        "before": asdict(old_candle),
                        "after": asdict(recovered),
                    }
                candles[token][source.time] = recovered
            completed_ranges += 1
            progress.stage("downloading", done=completed_ranges, total=total_ranges)
    if not candles[spot_token]:
        raise ValueError("Recovery has no spot source to seed Renko")

    progress.stage("rebuilding", done=completed_ranges, total=total_ranges)
    sessions = {local_time(s.opening).date(): s for s in calendar.sessions}
    rebuilt: dict[int, CandleBuilder] = {}
    outputs: dict[tuple[int, str], str] = {}
    bricks: list[Brick] = []
    missing: dict[int, int] = {}
    partial = oi_missing = 0
    for token, minutes in ((spot_token, 1), (future_token, 5)):
        builder = CandleBuilder(minutes, futures=token == future_token)
        rebuilt[token] = builder
        for candle in sorted(candles[token].values(), key=lambda c: c.time):
            source_session = sessions.get(candle.time.date())
            if source_session is None:
                raise ValueError("Calendar must cover all retained source candles")
            result = builder.import_completed(
                candle,
                session_open=source_session.opening,
                session_close=source_session.closing,
                cutoff=finish,
            )
            outputs[token, candle.time.astimezone(UTC).isoformat()] = encode(
                asdict(result)
            )
            partial += int(result.partial)
            oi_missing += int(token == future_token and result.oi is None)
            if token == spot_token:
                bricks.extend(store.renko.on_price(result.close, result.end))
        missing[token] = sum(
            (r.end - r.start) // timedelta(minutes=minutes) + 1
            for r in _missing_ranges(ranges[token], candles[token])
        )
        old = old_builders[token]
        # Completed history supersedes elapsed active fragments, never an
        # unfinished candle. Retain discarded fragments as checkpoint evidence.
        if old.current is not None and old.current.end > finish:
            if builder.day != old.current.time.date():
                builder.day = old.current.time.date()
                builder.weighted = builder.total_volume = Decimal(0)
            builder.current = replace(old.current, partial=True)
            builder.cumulative = old.cumulative
            builder.last_time = old.last_time
        elif ranges[token]:
            builder._closed_until = max(
                builder._closed_until or ranges[token][-1].completed_through,
                ranges[token][-1].completed_through,
            )
            builder.last_time = builder._closed_until
        builder.mark_gap()

    recovery = {
        "version": 1,
        "cutoff": finish,
        "futures_identity": futures_identity,
        "ranges": {t: [asdict(r) for r in ranges[t]] for t in tokens},
        "spot_missing": missing[spot_token],
        "futures_missing": missing[future_token],
        "retained_partial": partial,
        "oi_missing": oi_missing,
        "elapsed_fragments": {
            str(t): asdict(b.current)
            for t, b in old_builders.items()
            if b.current is not None and b.current.end <= finish
        },
        "entries_enabled": False,
        "correction_policy": "replace_partial" if correct_partial else "missing_only",
        "corrected_counts": {
            str(t): state.get("recovery", {}).get("corrected_counts", {}).get(str(t), 0)
            + sum(key[0] == t for key in corrections)
            for t in tokens
        },
    }
    # Preserve earlier fragment evidence across identical/repeated recovery runs.
    recovery["elapsed_fragments"] = (
        state.get("recovery", {}).get("elapsed_fragments", {})
        | recovery["elapsed_fragments"]
    )
    new_state = encode(
        {
            **state,
            "builders": {t: builder_state(b) for t, b in rebuilt.items()},
            "counts": {t: len(candles[t]) for t in tokens},
            "gap": True,
            "gaps": tracker.snapshot(),
            "last": asdict(store.renko.last) if store.renko.last else None,
            "last_timestamp": store.renko.last_timestamp,
            "next_index": store.renko.index,
            "recovery": recovery,
        }
    )
    brick_payloads = {b.index: encode(asdict(b)) for b in bricks}
    imported = (
        new_state != old_state
        or outputs != original
        or brick_payloads != original_bricks
    )
    progress.stage("committing", done=completed_ranges, total=total_ranges)
    try:
        with Session(engine) as db, db.begin():
            current = db.get(MarketCheckpoint, stream)
            if (
                current is None
                or current.revision != revision
                or current.configuration != store.configuration
                or current.state != old_state
            ):
                raise PersistenceError(
                    "Stream changed during recovery; stop duplicate writers"
                )
            if imported:
                changed = db.execute(
                    update(MarketCheckpoint)
                    .where(
                        MarketCheckpoint.stream == stream,
                        MarketCheckpoint.revision == revision,
                    )
                    .values(revision=revision + 1, state=new_state)
                )
                if cast(CursorResult[Any], changed).rowcount != 1:
                    raise PersistenceError("Stream changed during recovery")
                _stage_sources(
                    db,
                    stream,
                    spot_token,
                    future_token,
                    futures_identity,
                    fetched,
                    requested,
                    finish,
                    corrections,
                    client.retries,
                )
                db.execute(delete(StoredBrick).where(StoredBrick.stream == stream))
                db.execute(delete(StoredCandle).where(StoredCandle.stream == stream))
                for (token, stamp), payload in outputs.items():
                    db.add(
                        StoredCandle(
                            stream=stream, token=token, time=stamp, payload=payload
                        )
                    )
                for brick in bricks:
                    db.add(
                        StoredBrick(
                            stream=stream,
                            index=brick.index,
                            payload=encode(asdict(brick)),
                        )
                    )
    except SQLAlchemyError:
        raise PersistenceError("Recovery save failed; previous data retained") from None
    progress.committed(
        {t: max(c.end for c in candles[t].values()) for t in tokens if candles[t]},
        quality_pending=bool(
            sum(missing.values()) or partial or oi_missing or tracker.snapshot()
        ),
    )
    return RecoveryResult(
        revision + int(imported),
        imported,
        len(fetched[spot_token]) - sum(key[0] == spot_token for key in corrections),
        len(fetched[future_token]) - sum(key[0] == future_token for key in corrections),
        missing[spot_token],
        missing[future_token],
        partial,
        oi_missing,
        spot_corrected=sum(key[0] == spot_token for key in corrections),
        futures_corrected=sum(key[0] == future_token for key in corrections),
        request_retries=client.retries,
    )


def _stage_sources(
    db: Session,
    stream: str,
    spot: int,
    future: int,
    identity: str,
    fetched: dict[int, list[Candle]],
    requested: dict[int, tuple[HistoryRange, ...]],
    cutoff: datetime,
    corrections: dict[tuple[int, str], dict[str, Any]],
    request_retries: int,
) -> None:
    for token in (spot, future):
        if not fetched[token]:
            continue
        batch_id = uuid4().hex
        audit: dict[str, Any] = {
            "version": 1,
            "source": "kite_historical_recovery",
            "token": token,
            "cutoff": cutoff,
            "fetched_at": datetime.now(UTC),
            "identity": "NSE:NIFTY 50" if token == spot else identity,
            "ranges": [asdict(r) for r in requested[token]],
            "market_corrections": [
                value for key, value in corrections.items() if key[0] == token
            ],
            "staged_replacements": [],
            "request_retries": request_retries,
        }
        provenance = encode(audit)
        batch: HistoricalSpotBatch | HistoricalContextBatch
        if token == spot:
            batch = HistoricalSpotBatch(
                id=batch_id, stream=stream, token=token, provenance=provenance
            )
        else:
            batch = HistoricalContextBatch(
                id=batch_id, stream=stream, provenance=provenance
            )
        db.add(batch)
        db.flush()
        for candle in fetched[token]:
            stamp = candle.time.astimezone(UTC).isoformat()
            step = timedelta(minutes=1 if token == spot else 5)
            completed = (candle.time + step).astimezone(UTC).isoformat()
            existing = (
                db.get(HistoricalSpotCandle, (stream, token, stamp))
                if token == spot
                else db.get(
                    HistoricalContextCandle,
                    (stream, identity, "futures_5minute", stamp),
                )
            )
            if existing is not None:
                saved = json.loads(existing.payload)
                row = [
                    saved[k] for k in ("time", "open", "high", "low", "close", "volume")
                ]
                if token == future:
                    row.append(saved["oi"])
                if (
                    parse_candle(row, oi=token == future, allow_missing_oi=True)
                    != candle
                    or existing.completed_at != completed
                ):
                    if (token, stamp) not in corrections:
                        raise ValueError(
                            "Conflicting staged source; explicit correction required"
                        )
                    audit["staged_replacements"].append(
                        {
                            "time": stamp,
                            "before_payload": existing.payload,
                            "before_completed_at": existing.completed_at,
                            "before_batch_id": existing.batch_id,
                            "after_payload": encode(asdict(candle)),
                        }
                    )
                    existing.payload = encode(asdict(candle))
                    existing.completed_at = completed
                    existing.batch_id = batch_id
                continue
            payload = encode(asdict(candle))
            if token == spot:
                db.add(
                    HistoricalSpotCandle(
                        stream=stream,
                        token=token,
                        time=stamp,
                        completed_at=completed,
                        payload=payload,
                        batch_id=batch_id,
                    )
                )
            else:
                db.add(
                    HistoricalContextCandle(
                        stream=stream,
                        identity=identity,
                        kind="futures_5minute",
                        time=stamp,
                        completed_at=completed,
                        payload=payload,
                        batch_id=batch_id,
                    )
                )
        batch.provenance = encode(audit)
