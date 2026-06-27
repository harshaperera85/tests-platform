"""item_usage_event — longitudinal item-exposure history

Append-only per-(item, form, context) usage log. Cumulative exposure across
assemblies/administrations over time is derived by aggregating these rows, and
optionally fed back into assembly eligibility (opt-in).

Revision ID: 0009_item_usage_event
Revises: 0008_drop_test_status
Create Date: 2026-06-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_item_usage_event"
down_revision: str | None = "0008_drop_test_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_usage_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("form_id", sa.String(), nullable=False),
        sa.Column("test_id", sa.String(), nullable=True),
        sa.Column("pool_id", sa.String(), nullable=False),
        sa.Column("context", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["form.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_usage_event_item_id", "item_usage_event", ["item_id"])
    op.create_index("ix_item_usage_event_form_id", "item_usage_event", ["form_id"])
    op.create_index("ix_item_usage_event_test_id", "item_usage_event", ["test_id"])
    op.create_index("ix_item_usage_event_pool_id", "item_usage_event", ["pool_id"])
    op.create_index("ix_item_usage_event_context", "item_usage_event", ["context"])


def downgrade() -> None:
    op.drop_table("item_usage_event")
