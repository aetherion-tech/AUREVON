"""Dashboard lockout, mutation audit and durable operator alerts."""

import sqlalchemy as sa

from alembic import op

revision = "0006_dashboard_api"
down_revision = "0005_market_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_security_state",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.String(40), nullable=True),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("at", sa.String(40), nullable=False),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("status", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(32), nullable=False),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"])
    op.create_table(
        "dashboard_alerts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("source_key", sa.String(100), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("at", sa.String(40), nullable=False),
        sa.Column("acknowledged_at", sa.String(40), nullable=True),
    )
    op.create_index("ix_dashboard_alerts_at", "dashboard_alerts", ["at"])
    op.create_index(
        "ix_dashboard_alerts_source_key", "dashboard_alerts", ["source_key"]
    )


def downgrade() -> None:
    op.drop_table("dashboard_alerts")
    op.drop_table("audit_log")
    op.drop_table("dashboard_security_state")
