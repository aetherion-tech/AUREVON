"""Consistent SQLite backups and verified restore into a NEW database only."""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


def inspect_database(path: Path) -> dict[str, Any]:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Database integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Database foreign-key check failed")
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        counts = {
            name: db.execute(
                'SELECT count(*) FROM "' + name.replace('"', '""') + '"'
            ).fetchone()[0]
            for (name,) in tables
        }
        digest = hashlib.sha256(db.serialize()).hexdigest()
    return {"sha256": digest, "rows": counts}


def backup(source: Path, target: Path) -> dict[str, Any]:
    source = source.resolve(strict=True)
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents replacing an earlier baseline, even concurrently.
    with target.open("xb"):
        pass
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(target)) as dst:
                src.backup(dst)
        report = inspect_database(target)
        with target.with_suffix(target.suffix + ".manifest.json").open(
            "x", encoding="utf-8"
        ) as stream:
            json.dump(report, stream, indent=2)
        return report
    except Exception:
        target.unlink(missing_ok=True)
        raise


def restore(source: Path, target: Path) -> dict[str, Any]:
    manifest = source.with_suffix(source.suffix + ".manifest.json")
    expected = json.loads(manifest.read_text(encoding="utf-8"))
    if inspect_database(source) != expected:
        raise ValueError("Backup differs from its integrity manifest")
    result = backup(source, target)
    if result["rows"] != expected["rows"]:
        raise ValueError("Restore row counts differ")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore", "verify"])
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path, nargs="?")
    args = parser.parse_args()
    if args.action == "verify":
        result = inspect_database(args.source)
    else:
        if args.target is None:
            parser.error("A new target path is required")
        result = (backup if args.action == "backup" else restore)(
            args.source, args.target
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
