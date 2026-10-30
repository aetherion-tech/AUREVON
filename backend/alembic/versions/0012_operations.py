"""Nonexecuting shadow receipts and explicitly opt-in mark samples."""

import sqlalchemy as sa

from alembic import op

revision = "0012_operations"
down_revision = "0011_domain_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shadow_receipts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("stream", sa.String(160), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("at", sa.String(40), nullable=False),
        sa.Column("received_at", sa.String(40), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_index("ix_shadow_receipts_stream", "shadow_receipts", ["stream"])
    op.create_index("ix_shadow_receipts_index", "shadow_receipts", ["index"])
    op.create_table(
        "pnl_ticks",
        sa.Column("account_id", sa.String(40), primary_key=True),
        sa.Column("at", sa.String(40), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pnl_ticks")
    op.drop_index("ix_shadow_receipts_index", table_name="shadow_receipts")
    op.drop_index("ix_shadow_receipts_stream", table_name="shadow_receipts")
    op.drop_table("shadow_receipts")
