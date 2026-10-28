"""Retain accepted/rejected nonexecuting spread planning decisions."""

import sqlalchemy as sa

from alembic import op

revision = "0008_strategy"
down_revision = "0007_indicator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_decisions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("signal_id", sa.String(160), nullable=False),
        sa.Column("at", sa.String(40), nullable=False),
        *(
            sa.Column(name, sa.Text(), nullable=False)
            for name in ("input", "settings", "quotes", "payload")
        ),
    )
    op.create_index(
        "ix_strategy_decisions_signal_id", "strategy_decisions", ["signal_id"]
    )


def downgrade() -> None:
    op.drop_table("strategy_decisions")
