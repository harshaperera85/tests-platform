"""loft_session_record — persisted §4.4 LOFT conformance records (G5)

Append-only: one row per generated LOFT session form (band actuals, constraint
realization, engine, seed, draw provenance). Written by POST /loft/sessions
when persist_records is set; Sessions will persist per administration.

Revision ID: 0010_loft_session_record
Revises: 0009_item_usage_event
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_loft_session_record"
down_revision: str | None = "0009_item_usage_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loft_session_record",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blueprint_id", sa.String(), nullable=False),
        sa.Column("pool_id", sa.String(), nullable=False),
        sa.Column("engine", sa.String(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("session_index", sa.Integer(), nullable=False),
        sa.Column("item_ids", sa.JSON(), nullable=False),
        sa.Column("record", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["blueprint_id"], ["blueprint.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_loft_session_record_blueprint_id",
        "loft_session_record",
        ["blueprint_id"],
    )


def downgrade() -> None:
    op.drop_table("loft_session_record")
