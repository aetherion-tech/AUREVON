"""Explicit local account attachment; no automatic entries, quotes or capital."""

import asyncio
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import FastAPI
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.api.domain_contracts import SettingsUpdate
from app.api.domain_service import DomainService, PaperRuntime
from app.config import Settings
from app.db.models import PaperExecutionBook
from app.execution.models import PaperBook, Readiness
from app.execution.service import ACTIVE
from app.wallet.service import WalletService


async def wait_for_maintenance(settings: Settings) -> None:
    if not settings.local_ui_enabled:
        return
    flag = settings.local_ui_maintenance_file
    while flag.exists():
        payload = json.loads(flag.read_text(encoding="utf-8"))
        ack = flag.with_suffix(".ack.json")
        temporary = ack.with_name(ack.name + f".{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps({"nonce": payload["nonce"], "pid": os.getpid()}),
            encoding="utf-8",
        )
        os.replace(temporary, ack)
        await asyncio.sleep(0.25)


def attach_local_account(
    app: FastAPI, domain: DomainService, settings: Settings
) -> None:
    if not settings.local_ui_enabled:
        return
    engine = domain.engine
    required = {
        "paper_execution_books",
        "wallet_accounts",
        "domain_commands",
        "dashboard_settings_versions",
    }
    if not required <= set(inspect(engine).get_table_names()):
        app.state.local_ui_issue = "database_upgrade_required"
        return
    with Session(engine) as db:
        row = db.get(PaperExecutionBook, "PAPER")
        book = PaperBook.model_validate_json(row.payload) if row is not None else None
    if book is None or book.wallet_settings is None:
        app.state.local_ui_issue = "paper_account_setup_required"
        return
    # Never attach an empty-price owner to existing exposure. Recovery must
    # restore its matching price providers; this display owner cannot do that.
    if book.reserved or any(p.status in ACTIVE for p in book.positions.values()):
        app.state.local_ui_issue = "existing_exposure_requires_matching_owner"
        return
    wallet = WalletService(
        engine,
        domain.market.calendar.window(domain.market.clock()),
        book.fill_settings,
        book.risk_settings,
        settings=book.wallet_settings,
    )
    app.state.paper_execution = wallet
    selected = domain.settings.read()
    if (
        selected.settings.fills != wallet.fills
        or selected.settings.risk != wallet.risk
        or selected.settings.wallet != book.wallet_settings
    ):
        app.state.local_ui_issue = "saved_settings_require_owner_rebind"
        return

    def unavailable_catalog() -> Any:
        raise ValueError("Reference-verified contract owner is not attached")

    app.state.paper_runtime = PaperRuntime(
        wallet,
        selected,
        lambda at: Readiness(
            at=at,
            feed=False,
            authenticated=False,
            recovered=False,
            indicators=False,
            clock=False,
            event_blocked=True,
        ),
        unavailable_catalog,
        lambda: {},
        lambda: {},
        entries_allowed=False,
    )
    app.state.local_ui_issue = "paper_entries_locked_reference_gates"


def initialize_zero_account(domain: DomainService, at: datetime) -> None:
    """One-time explicit setup operation; never run as an automatic startup seed."""
    with Session(domain.engine) as db:
        row = db.get(PaperExecutionBook, "PAPER")
        existing = PaperBook.model_validate_json(row.payload) if row else None
    if existing is not None:
        if existing.ledger:
            return
        if (
            existing.positions
            or existing.reserved
            or existing.balance
            or existing.wallet_settings is None
            or existing.wallet_settings.initial_capital != 0
        ):
            raise ValueError(
                "Existing unfinished account requires explicit reconciliation"
            )
        # Resume a crash after the zero-settings/book commit but before INITIAL.
        resumed = WalletService(
            domain.engine,
            domain.market.calendar.window(at),
            existing.fill_settings,
            existing.risk_settings,
            settings=existing.wallet_settings,
        )
        resumed.initialize(at)
        return
    chosen = domain.settings.read()
    wallet_settings = chosen.settings.wallet.model_copy(
        update={"initial_capital": Decimal("0.00")}
    )
    chosen = domain.settings.update(
        SettingsUpdate(
            expected_revision=chosen.revision,
            settings=chosen.settings.model_copy(update={"wallet": wallet_settings}),
        ),
        command_key="local-ui-zero-account-v1",
    )
    wallet = WalletService(
        domain.engine,
        domain.market.calendar.window(at),
        chosen.settings.fills,
        chosen.settings.risk,
        settings=chosen.settings.wallet,
    )
    wallet.initialize(at)
