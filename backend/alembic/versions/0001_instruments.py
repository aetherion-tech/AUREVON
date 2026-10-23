"""Create daily instrument catalog tables."""

import sqlalchemy as sa

from alembic import op

revision = "0001_instruments"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("exchange", sa.String(10), primary_key=True),
        sa.Column("tradingsymbol", sa.String(100), primary_key=True),
        sa.Column("instrument_token", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column("strike", sa.Numeric(18, 6), nullable=False),
        sa.Column("tick_size", sa.Numeric(18, 6), nullable=False),
        sa.Column("lot_size", sa.Integer(), nullable=False),
        sa.Column("instrument_type", sa.String(10), nullable=False),
        sa.Column("segment", sa.String(20), nullable=False),
    )
    op.create_index(
        "ix_instruments_instrument_token", "instruments", ["instrument_token"]
    )
    op.create_index("ix_instruments_name", "instruments", ["name"])
    op.create_table(
        "instrument_snapshots",
        sa.Column("exchange", sa.String(10), primary_key=True),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("instrument_snapshots")
    op.drop_table("instruments")
