"""``blueprint`` table — a stored assembly specification (plan §8).

The full validated :class:`~app.schemas.blueprint.Blueprint` is persisted as JSON in
``spec``; the scalar columns are denormalized for listing/filtering.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONColumn, PkUuidMixin, TimestampMixin


class BlueprintRow(PkUuidMixin, TimestampMixin, Base):
    __tablename__ = "blueprint"

    name: Mapped[str] = mapped_column(default="untitled-blueprint")
    length: Mapped[int] = mapped_column()
    num_forms: Mapped[int] = mapped_column(default=1)
    #: full Blueprint pydantic dump (content constraints, TIF target, policies)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONColumn)
