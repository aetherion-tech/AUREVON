"""Command retry recovery and settings compare-and-swap; never infer activation."""

import hashlib
import re
from collections.abc import Callable
from threading import RLock

from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.api.domain_contracts import SettingsBundle, SettingsUpdate, SettingsView
from app.db.models import DashboardSettingsVersion, DomainCommand


class Commands:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.lock = RLock()

    def run(
        self, key: str, action: str, payload: str, operation: Callable[[], str]
    ) -> str:
        if not re.fullmatch(r"[A-Za-z0-9:_-]{1,160}", key):
            raise HTTPException(422)
        fingerprint = hashlib.sha256((action + ":" + payload).encode()).hexdigest()
        # One API worker; persistence plus domain idempotency also covers a
        # crash after a wallet commit but before command completion.
        with self.lock:
            with self.engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                with Session(bind=connection) as db:
                    row = db.get(DomainCommand, ("PAPER", key))
                    if row:
                        if row.fingerprint != fingerprint:
                            raise HTTPException(409)
                        if row.status is not None:
                            if row.status != 200:
                                raise HTTPException(row.status)
                            assert row.result is not None
                            return row.result
                    else:
                        db.add(
                            DomainCommand(
                                scope="PAPER",
                                key=key,
                                fingerprint=fingerprint,
                                result=None,
                                status=None,
                            )
                        )
                    db.flush()
                    connection.commit()
            try:
                result = operation()
            except (ValueError, KeyError, HTTPException) as error:
                status = (
                    error.status_code
                    if isinstance(error, HTTPException)
                    else 404
                    if isinstance(error, KeyError)
                    else 409
                )
                with Session(self.engine) as db, db.begin():
                    row = db.get(DomainCommand, ("PAPER", key))
                    assert row is not None
                    row.status = status
                raise HTTPException(status) from None
            with Session(self.engine) as db, db.begin():
                row = db.get(DomainCommand, ("PAPER", key))
                assert row is not None
                row.result, row.status = result, 200
            return result


class SettingsStore:
    def __init__(self, engine: Engine, defaults: SettingsBundle) -> None:
        self.engine, self.defaults = engine, defaults

    def _read(self, db: Session) -> SettingsView:
        row = db.scalar(
            select(DashboardSettingsVersion)
            .where(DashboardSettingsVersion.scope == "PAPER")
            .order_by(DashboardSettingsVersion.revision.desc())
            .limit(1)
        )
        return (
            SettingsView.model_validate_json(row.payload)
            if row
            else SettingsView(
                revision=0,
                settings=self.defaults,
                requires_rebuild=False,
                activation="defaults",
            )
        )

    def read(self) -> SettingsView:
        with Session(self.engine) as db:
            return self._read(db)

    def update(
        self, body: SettingsUpdate, command_key: str | None = None
    ) -> SettingsView:
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            with Session(bind=connection) as db:
                if command_key is not None:
                    completed = db.scalar(
                        select(DashboardSettingsVersion).where(
                            DashboardSettingsVersion.scope == "PAPER",
                            DashboardSettingsVersion.command_key == command_key,
                        )
                    )
                    if completed is not None:
                        result = SettingsView.model_validate_json(completed.payload)
                        if (
                            result.settings != body.settings
                            or result.revision != body.expected_revision + 1
                        ):
                            raise HTTPException(409)
                        return result
                prior = self._read(db)
                if prior.revision != body.expected_revision:
                    raise HTTPException(409)
                grid_changed = (
                    prior.settings.data != body.settings.data
                    or prior.settings.pine != body.settings.pine
                )
                if grid_changed and not body.rebuild:
                    raise HTTPException(409)
                result = SettingsView(
                    revision=prior.revision + 1,
                    settings=body.settings,
                    requires_rebuild=prior.requires_rebuild or grid_changed,
                    activation="owner_rebind_required",
                )
                db.add(
                    DashboardSettingsVersion(
                        scope="PAPER",
                        revision=result.revision,
                        payload=result.model_dump_json(),
                        command_key=command_key,
                    )
                )
                db.flush()
                connection.commit()
                return result
