"""Download candles using the existing encrypted daily Kite session."""

import argparse
from datetime import datetime
from pathlib import Path

from app.broker.kite_auth import AuthError, KiteAuth
from app.config import Settings
from app.market.historical import download, save_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", type=int, required=True)
    parser.add_argument("--start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--end", type=datetime.fromisoformat, required=True)
    parser.add_argument("--interval", choices=["minute", "5minute"], default="minute")
    parser.add_argument("--oi", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    auth = KiteAuth(Settings())
    try:
        candles = download(
            auth, args.token, args.start, args.end, interval=args.interval, oi=args.oi
        )
        if not candles:
            print("No completed candles returned; existing output preserved.")
            return 1
        save_csv(args.output, candles, args.interval)
        print(f"Saved {len(candles)} completed candles to {args.output}")
        return 0
    except (AuthError, ValueError, OSError) as error:
        message = error.message if isinstance(error, AuthError) else str(error)
        print(f"Download failed: {message}")
        return 2
    finally:
        auth.close()


if __name__ == "__main__":
    raise SystemExit(main())
