"""Stage historical spot candles with immutable download provenance."""

import sqlalchemy as sa

from alembic import op

revision = "0003_historical_spot"
down_revision = "0002_market_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_spot_batches",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("stream", sa.String(160), nullable=False),
        sa.Column("token", sa.Integer(), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=False),
    )
    op.create_table(
        "historical_spot_candles",
        sa.Column("stream", sa.String(160), primary_key=True),
        sa.Column("token", sa.Integer(), primary_key=True),
        sa.Column("time", sa.String(40), primary_key=True),
        sa.Column("completed_at", sa.String(40), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column(
            "batch_id",
            sa.String(32),
            sa.ForeignKey("historical_spot_batches.id"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("historical_spot_candles")
    op.drop_table("historical_spot_batches")
