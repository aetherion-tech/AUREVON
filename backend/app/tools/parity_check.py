"""Compare every reconstructed brick with a TradingView CSV export."""

import argparse
from decimal import InvalidOperation
from itertools import zip_longest
from pathlib import Path

from app.market.renko_builder import RenkoBuilder
from app.tools.replay import reference_bricks, replay


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    renko = commands.add_parser("renko")
    renko.add_argument("--csv", type=Path, required=True, help="TradingView brick CSV")
    renko.add_argument("--prices", type=Path, required=True, help="Source price CSV")
    renko.add_argument("--anchor", required=True)
    renko.add_argument("--box", default="50")
    renko.add_argument(
        "--mode", choices=["minute_close", "tick"], default="minute_close"
    )
    args = parser.parse_args(argv)
    try:
        expected = reference_bricks(args.csv)
        bricks = replay(args.prices, RenkoBuilder(args.box, args.anchor, args.mode))
        actual = [(brick.open, brick.close, brick.direction) for brick in bricks]
        if not expected or not actual:
            raise ValueError("both inputs must produce at least one brick")
    except (OSError, ValueError, InvalidOperation) as error:
        print(f"Input error: {error}")
        return 2
    mismatches = 0
    for index, (want, got) in enumerate(zip_longest(expected, actual)):
        if want != got:
            if mismatches == 0:
                print(f"First mismatch at brick {index}: expected={want}, got={got}")
            mismatches += 1
    print(f"Expected {len(expected)}, built {len(actual)}, mismatches {mismatches}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
