"""Shared column types / mixins for the ORM.

``JSONB`` on PostgreSQL (the production DB) with a portable ``JSON`` fallback so the
same models run under SQLite in tests.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

#: JSONB on Postgres, JSON elsewhere (SQLite test DB).
JSONColumn = JSON().with_variant(JSONB, "postgresql")


def new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PkUuidMixin:
    """String UUID primary key, stable and DB-agnostic."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
