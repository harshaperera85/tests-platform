"""index test.updated_at (GET /tests list sort)

FK/lookup columns are already indexed (blueprint_id, assembly_job_id, test_id,
audit action/entity_id). This adds the one missing hot-path index: the tests list
orders by updated_at desc.

Revision ID: 0006_test_updated_at_index
Revises: 0005_audit_event
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_test_updated_at_index"
down_revision: str | None = "0005_audit_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_test_updated_at", "test", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_test_updated_at", table_name="test")
