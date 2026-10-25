"""Stage contract-specific futures and spot daily context."""

import sqlalchemy as sa

from alembic import op

revision = "0004_historical_context"
down_revision = "0003_historical_spot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_context_batches",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("stream", sa.String(160), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=False),
    )
    op.create_table(
        "historical_context_candles",
        sa.Column("stream", sa.String(160), primary_key=True),
        sa.Column("identity", sa.String(160), primary_key=True),
        sa.Column("kind", sa.String(20), primary_key=True),
        sa.Column("time", sa.String(40), primary_key=True),
        sa.Column("completed_at", sa.String(40), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column(
            "batch_id",
            sa.String(32),
            sa.ForeignKey("historical_context_batches.id"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("historical_context_candles")
    op.drop_table("historical_context_batches")
