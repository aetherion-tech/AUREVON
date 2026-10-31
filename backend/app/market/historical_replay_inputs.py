"""Persist replay inputs in a separate directory; never attach a trading runtime."""

import json
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from app.market.historical_options import CoverageRequest, coverage, load_options


def prepare_inputs(source: Path, request: CoverageRequest, root: Path) -> str:
    """Copy bounded bytes, validate the copy, then publish an isolated run folder."""
    root.mkdir(parents=True, exist_ok=True)
    identity = uuid4().hex
    with tempfile.TemporaryDirectory(prefix=".preparing-", dir=root) as staging:
        folder = Path(staging)
        copied = folder / "options.json"
        with source.open("rb") as incoming, copied.open("xb") as outgoing:
            remaining = 50_000_000
            while chunk := incoming.read(min(65536, remaining + 1)):
                remaining -= len(chunk)
                if remaining < 0:
                    raise ValueError("historical option bundle exceeds byte limit")
                outgoing.write(chunk)
        bundle, digest = load_options(copied)
        manifest = {
            "version": 1,
            "id": identity,
            "state": "INPUTS_PREPARED",
            "mode": "HISTORICAL_REPLAY",
            "entries_enabled": False,
            "request": request.model_dump(mode="json"),
            "source_sha256": digest,
            "coverage": coverage(bundle, request),
        }
        (folder / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        # Same-volume directory rename publishes the complete pair together.
        folder.rename(root / identity)
    return identity


def inspect_inputs(root: Path, identity: str) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{32}", identity) is None:
        raise ValueError("invalid replay identity")
    folder = (root / identity).resolve()
    if folder.parent != root.resolve():
        raise ValueError("replay folder escapes input root")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    bundle, digest = load_options(folder / "options.json")
    if (
        manifest.get("version") != 1
        or manifest.get("id") != identity
        or manifest.get("state") != "INPUTS_PREPARED"
        or manifest.get("mode") != "HISTORICAL_REPLAY"
        or manifest.get("entries_enabled") is not False
        or digest != manifest.get("source_sha256")
    ):
        raise ValueError("replay input identity or integrity failure")
    request = CoverageRequest.model_validate(manifest["request"])
    # Recompute rather than trusting cached readiness or P&L fields.
    return {
        "id": identity,
        "request": request.model_dump(mode="json"),
        "source_sha256": digest,
        "coverage": coverage(bundle, request),
        "entries_enabled": False,
    }
