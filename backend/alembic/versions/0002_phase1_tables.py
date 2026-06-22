"""phase 1 data model: blueprint, assembly_job, form

Plan §8. Adds the three Phase 1 tables. JSONB on PostgreSQL for the spec / params /
result / item-id / TIF payloads.

Revision ID: 0002_phase1_tables
Revises: 0001_baseline
Create Date: 2026-06-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_phase1_tables"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "blueprint",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("length", sa.Integer(), nullable=False),
        sa.Column("num_forms", sa.Integer(), nullable=False),
        sa.Column("spec", _JSONB, nullable=False),
    )

    op.create_table(
        "assembly_job",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "blueprint_id",
            sa.String(length=36),
            sa.ForeignKey("blueprint.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("strategy", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("params", _JSONB, nullable=False),
        sa.Column("result", _JSONB, nullable=True),
    )
    op.create_index("ix_assembly_job_blueprint_id", "assembly_job", ["blueprint_id"])

    op.create_table(
        "form",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "blueprint_id",
            sa.String(length=36),
            sa.ForeignKey("blueprint.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assembly_job_id",
            sa.String(length=36),
            sa.ForeignKey("assembly_job.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("form_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("item_ids", _JSONB, nullable=False),
        sa.Column("tif_actual", _JSONB, nullable=False),
    )
    op.create_index("ix_form_blueprint_id", "form", ["blueprint_id"])
    op.create_index("ix_form_assembly_job_id", "form", ["assembly_job_id"])


def downgrade() -> None:
    op.drop_index("ix_form_assembly_job_id", table_name="form")
    op.drop_index("ix_form_blueprint_id", table_name="form")
    op.drop_table("form")
    op.drop_index("ix_assembly_job_blueprint_id", table_name="assembly_job")
    op.drop_table("assembly_job")
    op.drop_table("blueprint")
