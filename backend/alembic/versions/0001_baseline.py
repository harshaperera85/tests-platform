"""baseline (empty)

Initial migration establishing the Alembic version table. No domain tables yet —
the data model (plan §8) lands in Phase 1.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-22
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
