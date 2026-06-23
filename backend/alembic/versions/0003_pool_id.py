"""add pool_id to assembly_job and form

Records which item pool (catalog id, plan §8 item_pool_ref) a job assembled from
and a form's items resolve against. Additive, with a server_default so existing
rows backfill to the small smoke bank.

Revision ID: 0003_pool_id
Revises: 0002_phase1_tables
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_pool_id"
down_revision: str | None = "0002_phase1_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assembly_job",
        sa.Column(
            "pool_id", sa.String(), nullable=False, server_default="small_2pl"
        ),
    )
    op.add_column(
        "form",
        sa.Column(
            "pool_id", sa.String(), nullable=False, server_default="small_2pl"
        ),
    )


def downgrade() -> None:
    op.drop_column("form", "pool_id")
    op.drop_column("assembly_job", "pool_id")
