"""``audit_event`` table — append-only log of config/assembly/lock actions (plan §8).

Records who/what changed for traceability. Append-only: rows are never updated or
deleted by the application.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONColumn, PkUuidMixin, TimestampMixin


class AuditEventRow(PkUuidMixin, TimestampMixin, Base):
    __tablename__ = "audit_event"

    action: Mapped[str] = mapped_column(index=True)  # test.create, test.assemble, ...
    entity_type: Mapped[str] = mapped_column()  # test / form / ...
    entity_id: Mapped[str | None] = mapped_column(nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict)
