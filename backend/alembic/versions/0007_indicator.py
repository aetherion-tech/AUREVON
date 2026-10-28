"""Atomic Pine indicator checkpoints, results, candidates and trade events."""

import sqlalchemy as sa

from alembic import op

revision = "0007_indicator"
down_revision = "0006_dashboard_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indicator_checkpoints",
        sa.Column("stream", sa.String(160), primary_key=True),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_table(
        "indicator_results",
        sa.Column("stream", sa.String(160), primary_key=True),
        sa.Column("index", sa.Integer(), primary_key=True),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_table(
        "indicator_events",
        sa.Column("stream", sa.String(160), primary_key=True),
        sa.Column("index", sa.Integer(), primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("indicator_events")
    op.drop_table("indicator_results")
    op.drop_table("indicator_checkpoints")
