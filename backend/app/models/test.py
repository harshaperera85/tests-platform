"""``test`` table — the authoring entity that owns a linear test (plan §8).

A test carries its editable blueprint draft (``blueprint_spec`` JSON), the chosen
pool, an administration model, and a status/version. Assembling a test snapshots
the draft into an immutable ``blueprint`` row and produces ``assembly_job`` + ``form``
rows linked back via ``test_id``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONColumn, PkUuidMixin, TimestampMixin


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TestRow(PkUuidMixin, TimestampMixin, Base):
    __tablename__ = "test"

    name: Mapped[str] = mapped_column(default="Untitled test")
    administration_model: Mapped[str] = mapped_column(
        default="linear", server_default="linear"
    )
    status: Mapped[str] = mapped_column(
        default="draft", server_default="draft"
    )  # draft / review / locked / published
    pool_id: Mapped[str] = mapped_column(
        default="demo_mixed", server_default="demo_mixed"
    )
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    #: editable blueprint draft (Blueprint pydantic dump); None until first saved
    blueprint_spec: Mapped[dict[str, Any] | None] = mapped_column(
        JSONColumn, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
        index=True,  # GET /tests sorts by updated_at desc
    )
