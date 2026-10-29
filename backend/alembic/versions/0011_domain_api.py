"""Versioned settings, durable command intents and indexed decision projection."""

import json

import sqlalchemy as sa

from alembic import op

revision = "0011_domain_api"
down_revision = "0010_wallet"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "domain_decisions",
        sa.Column("scope", sa.String(120), primary_key=True),
        sa.Column("id", sa.String(240), primary_key=True),
        sa.Column("at", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_domain_decision_time", "domain_decisions", ["scope", "at", "id"]
    )
    op.create_table(
        "dashboard_settings_versions",
        sa.Column("scope", sa.String(120), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("command_key", sa.String(160), nullable=True),
    )
    op.create_index(
        "ix_settings_command",
        "dashboard_settings_versions",
        ["scope", "command_key"],
        unique=True,
    )
    op.create_table(
        "domain_commands",
        sa.Column("scope", sa.String(120), primary_key=True),
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("status", sa.Integer(), nullable=True),
    )
    connection = op.get_bind()

    def retain(
        scope: str,
        identity: str,
        signal: str,
        at: str,
        kind: str,
        accepted: bool,
        reasons: list[str],
        trade: str | None = None,
    ) -> None:
        payload = json.dumps(
            dict(
                id=identity,
                signal_id=signal,
                at=at,
                kind=kind,
                accepted=accepted,
                reasons=reasons,
                explanation="; ".join(reasons),
                trade_id=trade,
                executable=False,
            )
        )
        connection.execute(
            sa.text("INSERT INTO domain_decisions VALUES (:s,:i,:a,:k,:p)"),
            dict(s=scope, i=identity, a=at, k=kind, p=payload),
        )

    for row in connection.execute(
        sa.text("SELECT id,signal_id,at,payload FROM strategy_decisions")
    ).mappings():
        decision = json.loads(row["payload"])
        retain(
            "PAPER",
            row["id"],
            row["signal_id"],
            row["at"],
            "PREVIEW",
            decision["accepted"],
            [decision["reason"]],
        )
    for row in connection.execute(
        sa.text("SELECT id,payload FROM paper_execution_books")
    ).mappings():
        book = json.loads(row["payload"])
        for key, reject in book.get("rejects", {}).items():
            retain(
                row["id"],
                "risk:" + key,
                reject["signal_id"],
                reject["at"],
                "RISK_REJECT",
                False,
                reject["reasons"],
            )
        for position in book.get("positions", {}).values():
            plan = position["plan"]
            retain(
                row["id"],
                "admission:" + position["decision_id"],
                plan["signal"]["signal_id"],
                plan["planned_at"],
                "PAPER_ADMISSION",
                True,
                ["accepted"],
                position["id"],
            )


def downgrade() -> None:
    for name in ("domain_commands", "dashboard_settings_versions", "domain_decisions"):
        op.drop_table(name)
