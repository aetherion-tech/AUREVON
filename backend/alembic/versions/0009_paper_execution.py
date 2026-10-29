"""Atomic exact-decimal paper book, orders, fills, transitions and ledger."""

import sqlalchemy as sa

from alembic import op

revision = "0009_paper_execution"
down_revision = "0008_strategy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_execution_books",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("paper_execution_books")
