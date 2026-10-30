"""Explicit guarded backup/migration/zero-account setup for the local dashboard."""

import argparse
import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from app.config import BACKEND_DIR, Settings
from app.market.lifecycle_state import ProcessLease
from app.tools.backup import backup, inspect_database


def set_local_ui_enabled(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == "LOCAL_UI_ENABLED":
            lines[i] = "LOCAL_UI_ENABLED=true"
            found = True
    if not found:
        lines.append("LOCAL_UI_ENABLED=true")
    # Atomic replacement; never print/replace any other setting or credential.
    temporary = path.with_name(path.name + ".local-ui.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        if os.name == "nt" and path.exists():
            import win32security  # type: ignore[import-untyped]

            descriptor = win32security.GetFileSecurity(
                str(path), win32security.DACL_SECURITY_INFORMATION
            )
            control, _ = descriptor.GetSecurityDescriptorControl()
            flags = win32security.DACL_SECURITY_INFORMATION
            flags |= (
                win32security.PROTECTED_DACL_SECURITY_INFORMATION
                if control & win32security.SE_DACL_PROTECTED
                else win32security.UNPROTECTED_DACL_SECURITY_INFORMATION
            )
            win32security.SetFileSecurity(str(temporary), flags, descriptor)
        stream.write("\n".join(lines) + "\n")
    os.replace(temporary, path)


def run() -> None:
    settings = Settings()
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        raise ValueError("Local UI recovery requires a file-backed SQLite database")
    database = Path(url.database).resolve(strict=True)
    flag = settings.local_ui_maintenance_file
    flag.parent.mkdir(parents=True, exist_ok=True)
    setup_owner = ProcessLease(flag.with_suffix(".setup.lock"))
    setup_owner.acquire()
    market_owner = ProcessLease(settings.market_lock_file)
    try:
        # Fail BEFORE pausing an actual feed owner or changing any configuration.
        market_owner.acquire()
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
            tables = {
                r[0]
                for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if "paper_execution_books" in tables:
                from app.execution.models import PaperBook
                from app.execution.service import ACTIVE

                for (payload,) in db.execute(
                    "SELECT payload FROM paper_execution_books"
                ):
                    book = PaperBook.model_validate_json(payload)
                    if book.reserved or any(
                        p.status in ACTIVE for p in book.positions.values()
                    ):
                        raise ValueError(
                            "Existing exposure requires its matching owner; "
                            "setup refused"
                        )
        market_owner.release()
        nonce = json.loads(flag.read_text())["nonce"] if flag.exists() else uuid4().hex
        if not flag.exists():
            with flag.open("x", encoding="utf-8") as stream:
                json.dump({"nonce": nonce, "purpose": "local_ui_setup"}, stream)
        set_local_ui_enabled(BACKEND_DIR / ".env")
        with httpx.Client(timeout=2, trust_env=False) as client:
            try:
                running = (
                    client.get("http://127.0.0.1:8000/api/health").status_code == 200
                )
            except httpx.HTTPError:
                running = False
        # Existing operator uses uvicorn --reload. Its new child acknowledges
        # maintenance BEFORE opening market services or attaching a DB account.
        os.utime(BACKEND_DIR / "app" / "main.py", None)
        if running:
            print(
                "Waiting for the existing reload owner to pause gracefully...",
                flush=True,
            )
            deadline = time.monotonic() + 60
            ack = flag.with_suffix(".ack.json")
            while time.monotonic() < deadline:
                if ack.exists() and json.loads(ack.read_text()).get("nonce") == nonce:
                    break
                time.sleep(0.25)
            else:
                raise ValueError(
                    "Owner did not acknowledge pause; stop its terminal safely, "
                    "then rerun setup. Database was not migrated."
                )
        market_owner.acquire()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        target = BACKEND_DIR / "data" / "backups" / f"local-ui-{stamp}-{nonce[:8]}.db"
        prior = backup(database, target)
        if inspect_database(target) != prior:
            raise ValueError("Backup verification failed")
        print(
            "Verified immutable database backup; applying additive migrations...",
            flush=True,
        )
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        command.upgrade(config, "head")
        from app.api.local_owner import initialize_zero_account
        from app.main import create_app

        app = create_app(Settings())
        try:
            initialize_zero_account(
                app.state.domain_service, datetime.now(timezone.utc)
            )
        finally:
            app.state.database_engine.dispose()
            app.state.market_service.auth.close()
        receipt = {
            "at": datetime.now(timezone.utc).isoformat(),
            "backup": str(target),
            "preserved_rows": prior["rows"],
            "revision": "0012_operations",
            "initial_simulated_capital": "0.00",
            "entries_enabled": False,
            "market_service_enabled_unchanged": settings.market_service_enabled,
        }
        receipt_path = target.with_suffix(".setup.json")
        with receipt_path.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2)
        market_owner.release()
        flag.unlink()
        print(
            json.dumps(
                {
                    "status": "setup_complete",
                    "receipt": str(receipt_path),
                    "paper_entries": "blocked",
                    "next": "Sign in, complete Kite login, then Start market data",
                }
            ),
            flush=True,
        )
    finally:
        market_owner.release()
        setup_owner.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", required=True)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
