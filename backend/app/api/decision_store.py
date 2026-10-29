"""Persist one indexed public decision alongside its domain transaction."""

from typing import Any

from sqlalchemy.orm import Session

from app.api.domain_contracts import DecisionView
from app.db.models import DomainDecision


def retain(
    db: Session,
    scope: str,
    identity: str,
    signal_id: str,
    at: Any,
    kind: str,
    accepted: bool,
    reasons: list[str],
    trade_id: str | None = None,
) -> None:
    value = DecisionView.model_validate(
        dict(
            id=identity,
            signal_id=signal_id,
            at=at,
            kind=kind,
            accepted=accepted,
            reasons=reasons,
            trade_id=trade_id,
            explanation="; ".join(reasons),
        )
    )
    if db.get(DomainDecision, (scope, identity)) is None:
        db.add(
            DomainDecision(
                scope=scope,
                id=identity,
                at=value.at.isoformat(),
                kind=kind,
                payload=value.model_dump_json(),
            )
        )
