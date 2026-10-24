"""Persist completed candles, Renko bricks, and atomic restart checkpoints."""

import sqlalchemy as sa

from alembic import op

revision = "0002_market_state"
down_revision = "0001_instruments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_checkpoints",
        sa.Column("stream", sa.String(160), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
    )
    op.create_table(
        "market_candles",
        sa.Column("stream", sa.String(160), primary_key=True),
        sa.Column("token", sa.Integer(), primary_key=True),
        sa.Column("time", sa.String(40), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_table(
        "renko_bricks",
        sa.Column("stream", sa.String(160), primary_key=True),
        sa.Column("index", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("renko_bricks")
    op.drop_table("market_candles")
    op.drop_table("market_checkpoints")
