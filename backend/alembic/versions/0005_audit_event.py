"""audit_event table (append-only)

Plan §8 — log of config/assembly/lock actions for traceability.

Revision ID: 0005_audit_event
Revises: 0004_tests
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_audit_event"
down_revision: str | None = "0004_tests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("detail", _JSONB, nullable=False),
    )
    op.create_index("ix_audit_event_action", "audit_event", ["action"])
    op.create_index("ix_audit_event_entity_id", "audit_event", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_event_entity_id", table_name="audit_event")
    op.drop_index("ix_audit_event_action", table_name="audit_event")
    op.drop_table("audit_event")
