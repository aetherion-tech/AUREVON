"""Validate an offline actual-option-depth bundle; never touch live state."""

import argparse
import json
from pathlib import Path

from app.market.historical_options import CoverageRequest, coverage, load_options
from app.market.historical_replay_inputs import inspect_inputs, prepare_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument(
        "--runs-dir", type=Path, help="Optional isolated replay input store"
    )
    parser.add_argument("--start", required=True, help="ISO timestamp with timezone")
    parser.add_argument("--end", required=True, help="ISO timestamp with timezone")
    args = parser.parse_args()
    if args.runs_dir is not None and args.bundle is None:
        parser.error("--runs-dir requires --bundle")
    try:
        request = CoverageRequest(start=args.start, end=args.end)
    except ValueError:
        parser.error("use ordered ISO timestamps with explicit timezones")
    if args.bundle is None:
        result: dict[str, object] = {
            "status": "BLOCKED",
            "blockers": ["historical_option_bundle_not_supplied"],
            "option_pnl": None,
            "estimated_price_fallback": False,
        }
    else:
        try:
            bundle, digest = load_options(args.bundle)
            result = coverage(bundle, request) | {"sha256": digest}
            if args.runs_dir is not None:
                identity = prepare_inputs(args.bundle, request, args.runs_dir)
                result = inspect_inputs(args.runs_dir, identity)
        except (ValueError, OSError):
            result = {"status": "BLOCKED", "blockers": ["invalid_option_bundle"]}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
