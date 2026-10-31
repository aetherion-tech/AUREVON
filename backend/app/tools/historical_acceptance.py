"""Bounded real historical-download evidence; no orders, feed or database writes."""

import argparse
import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from app.broker.kite_auth import IST, KiteAuth
from app.config import Settings
from app.market.exchange_calendar import ExchangeCalendar
from app.market.historical import HistoricalClient, download, save_csv


def verify(
    client: HistoricalClient,
    token: int,
    start: datetime,
    closing: datetime,
    interval: Literal["minute", "5minute"],
    *,
    oi: bool,
    destination: Path,
) -> dict[str, Any]:
    duration = timedelta(minutes=1 if interval == "minute" else 5)
    returned = download(
        client, token, start, closing, interval=interval, oi=oi, allow_missing_oi=True
    )
    # Compare completed bars in [opening, closing). Request the next boundary
    # explicitly so a provider-exclusive end does not omit the last full bar.
    candles = [c for c in returned if c.time + duration <= closing]
    expected = []
    cursor = start
    while cursor < closing:
        expected.append(cursor)
        cursor += duration
    if [c.time for c in candles] != expected:
        raise ValueError("Historical coverage differs from the complete session grid")
    # Independently request an overlapping two-bar half-open window.
    limit = start + duration * 2
    repeated = download(
        client,
        token,
        start,
        limit,
        interval=interval,
        oi=oi,
        allow_missing_oi=True,
    )
    boundary = [c for c in repeated if c.time + duration <= limit]
    if boundary != candles[:2]:
        raise ValueError("Repeated boundary window disagrees with original candles")
    save_csv(destination, candles, interval)
    return {
        "token": token,
        "interval": interval,
        "candles": len(candles),
        "opening_time_first": candles[0].time.isoformat(),
        "opening_time_last": candles[-1].time.isoformat(),
        "completion_time_last": (candles[-1].time + duration).isoformat(),
        "overlapping_boundary_repeat_matches": True,
        "request_end": closing.isoformat(),
        "comparison_range": "half-open completed processing session",
        "returned_boundary_bars_outside_session": len(returned) - len(candles),
        "oi_requested": oi,
        "oi_present": sum(c.oi is not None for c in candles),
        "oi_positive": sum(c.oi is not None and c.oi > 0 for c in candles),
        "volume_positive": sum(c.volume > 0 for c in candles),
        "csv": str(destination),
        "csv_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "raw_values_hash": hashlib.sha256(
            json.dumps(
                [asdict(c) for c in candles], default=str, sort_keys=True
            ).encode()
        ).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--spot-token", type=int, required=True)
    parser.add_argument("--future-token", type=int, required=True)
    parser.add_argument("--future-symbol", required=True)
    parser.add_argument("--future-expiry", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    start = datetime.combine(args.date, datetime.min.time(), IST)
    session = ExchangeCalendar(settings.market_calendar_dir).session(start)
    if session is None or session.closing >= datetime.now(IST):
        raise ValueError("A completed sourced exchange session is required")
    if args.future_expiry < args.date or args.spot_token == args.future_token:
        raise ValueError("Invalid contract expiry or token identities")
    args.output.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "status": "RUNNING",
        "task": "QA-07-01",
        "date": args.date.isoformat(),
        "evidence": "ACTUAL_AUTHENTICATED_KITE_HISTORICAL",
        "future_symbol": args.future_symbol,
        "future_expiry": args.future_expiry.isoformat(),
        "operator_state_changed": False,
        "formal_sessions": 0,
        "g1_accepted": False,
    }
    # Authentication may discard an expired copy; never discard the operator file.
    with tempfile.TemporaryDirectory(prefix="aurevon-history-auth-") as folder:
        copied = Path(folder) / "session.bin"
        if settings.kite_session_file.exists():
            shutil.copyfile(settings.kite_session_file, copied)
        auth = KiteAuth(settings.model_copy(update={"kite_session_file": copied}))
        try:
            if not auth.status().authenticated:
                raise ValueError("Actual authenticated broker session required")
            requests: tuple[
                tuple[str, int, Literal["minute", "5minute"], bool], ...
            ] = (
                ("spot", args.spot_token, "minute", False),
                ("future", args.future_token, "5minute", True),
            )
            for label, token, interval, oi in requests:
                report[label] = verify(
                    auth,
                    token,
                    session.opening,
                    session.closing,
                    interval,
                    oi=oi,
                    destination=args.output / f"{label}.csv",
                )
            report["status"] = "PASS"
        except Exception:
            report["status"] = "FAILED"
            raise
        finally:
            auth.close()
            (args.output / "receipt.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
