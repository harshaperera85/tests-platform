"""form lifecycle: form.lifecycle_state + form_review_event sign-off trail

Adds the cross-model governance spine: a lifecycle state on every assembled form
(draft → content_review → psychometric_review → approved → published) and an
append-only sign-off table recording each transition's actor/role/comment.

Revision ID: 0007_form_lifecycle
Revises: 0006_test_updated_at_index
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_form_lifecycle"
down_revision: str | None = "0006_test_updated_at_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "form",
        sa.Column(
            "lifecycle_state",
            sa.String(),
            nullable=False,
            server_default="draft",
        ),
    )
    op.create_index("ix_form_lifecycle_state", "form", ["lifecycle_state"])

    op.create_table(
        "form_review_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("from_state", sa.String(), nullable=False),
        sa.Column("to_state", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False, server_default="anonymous"),
        sa.Column("actor_role", sa.String(), nullable=True),
        sa.Column("comment", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["form_id"], ["form.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_form_review_event_form_id", "form_review_event", ["form_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_form_review_event_form_id", table_name="form_review_event")
    op.drop_table("form_review_event")
    op.drop_index("ix_form_lifecycle_state", table_name="form")
    op.drop_column("form", "lifecycle_state")
