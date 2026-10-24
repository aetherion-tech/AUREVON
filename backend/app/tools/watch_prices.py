"""Standalone market-data monitor. Run one process; Ctrl+C stops it."""

import argparse
import asyncio
import json
from pathlib import Path

from app.broker.kite_auth import AuthError, KiteAuth
from app.broker.kite_ticker import TickerWorker
from app.config import BACKEND_DIR, Settings
from app.db.session import database_engine
from app.market.persistence import MarketPersistence
from app.market.tick_recording import TickRecorder


async def watch(
    auth: KiteAuth,
    spot: int,
    future: int,
    record_dir: Path,
    persistence: MarketPersistence | None = None,
) -> None:
    worker = TickerWorker(
        auth.create_ticker(),
        spot,
        future,
        recorder=TickRecorder(record_dir, spot, future),
        persistence=persistence,
    )
    try:
        await worker.start()
        while True:
            assert worker.task is not None
            drain = asyncio.create_task(worker.queue.join())
            try:
                done, _ = await asyncio.wait(
                    [drain, worker.task], return_when=asyncio.FIRST_COMPLETED
                )
                if worker.task in done:
                    await worker.task
            finally:
                drain.cancel()
            worker.advance_candles()
            print(json.dumps(worker.status(), default=str), flush=True)
            if worker.exhausted:
                raise RuntimeError("Reconnect attempts exhausted; restart after login")
            await asyncio.sleep(5)
    finally:
        await worker.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spot-token", type=int, required=True)
    parser.add_argument("--future-token", type=int, required=True)
    parser.add_argument(
        "--record-dir", type=Path, default=BACKEND_DIR / "data" / "ticks"
    )
    parser.add_argument(
        "--stream", help="Enable database persistence under this stream name"
    )
    args = parser.parse_args()
    settings = Settings()
    auth = KiteAuth(settings)
    engine = None
    try:
        persistence = None
        if args.stream:
            if settings.renko_anchor is None or settings.renko_mode != "minute_close":
                raise ValueError(
                    "Persistence requires RENKO_ANCHOR and minute_close mode"
                )
            engine = database_engine(settings.database_url)
            persistence = MarketPersistence(
                engine,
                args.stream,
                args.spot_token,
                args.future_token,
                box=settings.renko_box,
                anchor=settings.renko_anchor,
            )
        asyncio.run(
            watch(
                auth, args.spot_token, args.future_token, args.record_dir, persistence
            )
        )
    except KeyboardInterrupt:
        return 0
    except (AuthError, ValueError, RuntimeError):
        print(
            "Price feed stopped. Check login, tokens, connectivity, "
            "recording/database storage, migrations, and Renko settings."
        )
        return 1
    finally:
        auth.close()
        if engine is not None:
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
