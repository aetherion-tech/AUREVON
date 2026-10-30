"""Bounded synthetic synchronous-path baseline, never a live latency acceptance."""

import argparse
import json
import math
import platform
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.broker.kite_ticker import TickerWorker
from app.db.models import Base, StoredBrick
from app.db.session import database_engine
from app.indicator.persistence import IndicatorRepository
from app.market.persistence import MarketPersistence, brick_from
from app.market.renko_builder import IST


def benchmark(count: int = 500) -> dict[str, Any]:
    if not 100 <= count <= 2000:
        raise ValueError("Use 100 to 2000 synthetic ticks")
    with tempfile.TemporaryDirectory(prefix="aurevon-benchmark-") as folder:
        engine = database_engine(f"sqlite:///{Path(folder).as_posix()}/benchmark.db")
        Base.metadata.create_all(engine)
        stream = "synthetic-performance"
        store = MarketPersistence(engine, stream, 111, 222, anchor="23900")
        worker = TickerWorker(None, 111, 222, persistence=store)
        indicator = IndicatorRepository(engine, stream)
        samples: list[float] = []
        brick_samples: list[float] = []
        storage_samples: list[float] = []
        indicator_samples: list[float] = []
        last = -1
        start = datetime(2026, 10, 28, 9, 30, tzinfo=IST)
        try:
            for i in range(count):
                at = start + timedelta(seconds=i * 6)
                tick = {
                    "instrument_token": 111,
                    "exchange_timestamp": at,
                    "last_price": 23900 + (i // 10) * 50,
                }
                began = perf_counter()
                before = worker.accepted
                worker._accept(tick, at)
                stored = perf_counter()
                if worker.accepted != before + 1:
                    raise ValueError("Synthetic benchmark tick was not accepted")
                with Session(engine) as db:
                    rows = list(
                        db.scalars(
                            select(StoredBrick)
                            .where(
                                StoredBrick.stream == stream,
                                StoredBrick.index > last,
                            )
                            .order_by(StoredBrick.index)
                        )
                    )
                for row in rows:
                    indicator.process(brick_from(json.loads(row.payload)))
                    last = row.index
                calculated = perf_counter()
                elapsed = (perf_counter() - began) * 1000
                samples.append(elapsed)
                storage_samples.append((stored - began) * 1000)
                if rows:
                    brick_samples.append(elapsed)
                    indicator_samples.append((calculated - stored) * 1000)
        finally:
            engine.dispose()

    def summary(values: list[float]) -> dict[str, float | int | None]:
        ordered = sorted(values)
        return {
            "samples": len(values),
            "p50_ms": ordered[len(values) // 2] if values else None,
            "p95_ms": ordered[max(0, math.ceil(len(values) * 0.95) - 1)]
            if values
            else None,
            "max_ms": max(values) if values else None,
        }

    return {
        "evidence": "SYNTHETIC_BASELINE_ONLY",
        "platform": platform.platform(),
        "ticks": count,
        "completed_bricks": last + 1,
        "input": "synthetic spot ticks six seconds apart, executed as a burst",
        "measured": (
            "normalized tick through SQLite minute-close brick and indicator commits"
        ),
        "all_ticks": summary(samples),
        "brick_emitting_ticks": summary(brick_samples),
        "market_storage": summary(storage_samples),
        "indicator_and_readback_on_brick": summary(indicator_samples),
        "brick_to_dispatch_ms": None,
        "representative_load_verified": False,
        "limitations": [
            "No network/queue wait or option fanout",
            "No managed signal-to-order owner",
            "Short prefix; not a twenty-day warmed history",
            "Not QA-19-14 acceptance",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticks", type=int, default=500)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = benchmark(args.ticks)
    content = json.dumps(result, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(content)
    print(content)


if __name__ == "__main__":
    main()
