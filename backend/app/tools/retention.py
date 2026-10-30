"""Archive explicitly sealed recording runs while retaining their raw evidence."""

import argparse
import gzip
import hashlib
import json
import shutil
from datetime import date, timedelta
from pathlib import Path


def compress_sealed(root: Path, today: date, *, apply: bool = False) -> list[str]:
    planned: list[str] = []
    if not root.exists():
        return planned
    base = root.resolve(strict=True)
    for run in sorted(root.iterdir()):
        # The operator seals only STOPPED runs, after copying their provenance.
        # Never infer inactivity from mtime; an old file can belong to an owner.
        if run.is_symlink() or not run.is_dir() or not (run / "SEALED.json").is_file():
            continue
        manifest = json.loads((run / "SEALED.json").read_text(encoding="utf-8"))
        for name, digest in manifest.get("sha256", {}).items():
            raw = (run / name).resolve(strict=True)
            if not raw.is_relative_to(base) or not raw.is_relative_to(run.resolve()):
                raise ValueError("Sealed recording escapes its run directory")
            if raw.suffix != ".jsonl" or date.fromisoformat(raw.stem) >= today:
                continue
            if hashlib.sha256(raw.read_bytes()).hexdigest() != digest:
                raise ValueError("Sealed recording differs from evidence manifest")
            archive = raw.with_suffix(".jsonl.gz")
            if archive.exists():
                with gzip.open(archive, "rb") as existing:
                    if hashlib.sha256(existing.read()).hexdigest() != digest:
                        raise ValueError("Compressed recording failed verification")
                continue
            planned.append(str(raw.relative_to(base)))
            if apply:
                with archive.open("xb") as target:
                    with (
                        raw.open("rb") as source,
                        gzip.GzipFile(fileobj=target, mode="wb") as zipped,
                    ):
                        shutil.copyfileobj(source, zipped)
                with gzip.open(archive, "rb") as verified:
                    if hashlib.sha256(verified.read()).hexdigest() != digest:
                        raise ValueError("Compressed recording failed verification")
    return planned


def expired_pnl_ticks(at: date, day: date) -> bool:
    """Boundary policy only: financial projections/audits are never deleted."""
    return day < at - timedelta(days=90)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--day", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "apply": args.apply,
                "recordings": compress_sealed(args.root, args.day, apply=args.apply),
                "raw_evidence_deleted": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
