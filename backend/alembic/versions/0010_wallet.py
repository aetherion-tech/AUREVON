"""Scoped exact-text wallet ledger, trade history and period projections."""

import sqlalchemy as sa

from alembic import op

revision = "0010_wallet"
down_revision = "0009_paper_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wallet_reconciliation_runs",
        sa.Column("account_id", sa.String(120), primary_key=True),
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("at", sa.String(40), nullable=False),
        sa.Column("status", sa.String(5), nullable=False),
    )
    op.create_table(
        "wallet_accounts",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("user_id", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("balance", sa.String(40), nullable=False),
        sa.Column("reserved", sa.String(40), nullable=False),
    )
    op.create_index(
        "ix_wallet_scope", "wallet_accounts", ["user_id", "mode"], unique=True
    )
    op.create_table(
        "wallet_ledger",
        sa.Column("account_id", sa.String(120), primary_key=True),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(240), nullable=False),
        sa.Column("at", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_wallet_ledger_key", "wallet_ledger", ["account_id", "key"], unique=True
    )
    op.create_index(
        "ix_wallet_ledger_time", "wallet_ledger", ["account_id", "at", "sequence"]
    )
    op.create_table(
        "paper_trade_summaries",
        sa.Column("account_id", sa.String(120), primary_key=True),
        sa.Column("trade_id", sa.String(80), primary_key=True),
        *(
            sa.Column(name, sa.String(size), nullable=False)
            for name, size in (
                ("closed_at", 40),
                ("day", 10),
                ("family", 5),
                ("result", 10),
            )
        ),
        sa.Column("direction", sa.Integer(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_paper_history_time",
        "paper_trade_summaries",
        ["account_id", "closed_at", "trade_id"],
    )
    op.create_index(
        "ix_paper_history_filters",
        "paper_trade_summaries",
        ["account_id", "family", "direction", "grade", "result", "day"],
    )
    op.create_table(
        "paper_daily_pnl",
        sa.Column("account_id", sa.String(120), primary_key=True),
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_table(
        "wallet_periods",
        sa.Column("account_id", sa.String(120), primary_key=True),
        sa.Column("kind", sa.String(10), primary_key=True),
        sa.Column("start", sa.String(10), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    for name in (
        "wallet_reconciliation_runs",
        "wallet_periods",
        "paper_daily_pnl",
        "paper_trade_summaries",
        "wallet_ledger",
        "wallet_accounts",
    ):
        op.drop_table(name)
