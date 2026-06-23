"""tests resource: test table + test_id on assembly_job and form

Plan §8. Adds the authoring `test` entity (owns the editable blueprint draft, pool,
status/version) and links jobs/forms back to it. Additive.

Revision ID: 0004_tests
Revises: 0003_pool_id
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_tests"
down_revision: str | None = "0003_pool_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "test",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "administration_model", sa.String(), nullable=False, server_default="linear"
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("pool_id", sa.String(), nullable=False, server_default="demo_mixed"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("blueprint_spec", _JSONB, nullable=True),
    )

    for table in ("assembly_job", "form"):
        op.add_column(
            table,
            sa.Column(
                "test_id",
                sa.String(length=36),
                sa.ForeignKey("test.id", ondelete="CASCADE"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_test_id", table, ["test_id"])


def downgrade() -> None:
    for table in ("form", "assembly_job"):
        op.drop_index(f"ix_{table}_test_id", table_name=table)
        op.drop_column(table, "test_id")
    op.drop_table("test")
