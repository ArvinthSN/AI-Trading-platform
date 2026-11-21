"""Create owner-scoped market watchlists.

Revision ID: 20261121_01
Revises:
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261121_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_watchlists",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_market_watchlist_owner_name"),
    )
    op.create_index(
        "ix_market_watchlists_owner_id",
        "market_watchlists",
        ["owner_id"],
        unique=False,
    )
    op.create_table(
        "market_watchlist_instruments",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["market_watchlists.id"],
            name="fk_market_watchlist_instruments_watchlist_id_market_watchlists",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("watchlist_id", "symbol", name="uq_market_watchlist_symbol"),
    )
    op.create_index(
        "ix_market_watchlist_instruments_watchlist_id",
        "market_watchlist_instruments",
        ["watchlist_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_watchlist_instruments_watchlist_id",
        table_name="market_watchlist_instruments",
    )
    op.drop_table("market_watchlist_instruments")
    op.drop_index("ix_market_watchlists_owner_id", table_name="market_watchlists")
    op.drop_table("market_watchlists")
