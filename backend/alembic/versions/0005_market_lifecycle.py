"""Persist managed lifecycle/session context without altering market checkpoints."""

import sqlalchemy as sa

from alembic import op

revision = "0005_market_lifecycle"
down_revision = "0004_historical_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_lifecycle_state",
        sa.Column("key", sa.String(240), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("market_lifecycle_state")
