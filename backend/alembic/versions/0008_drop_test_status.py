"""drop test.status — editability/status derived from form lifecycle

The manual lock/unlock (test.status = draft/locked) is retired: a test's status and
editability are now DERIVED from its forms' lifecycle states (single source of
truth — services/form_lifecycle). The column served only the manual freeze, which
the form-lifecycle governance (0007) supersedes.

Revision ID: 0008_drop_test_status
Revises: 0007_form_lifecycle
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_drop_test_status"
down_revision: str | None = "0007_form_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("test", "status")


def downgrade() -> None:
    op.add_column(
        "test",
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="draft",
        ),
    )
