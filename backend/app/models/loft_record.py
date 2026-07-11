"""``loft_session_record`` — persisted §4.4 conformance records (G5).

Append-only: one row per generated LOFT session form, carrying the full
conformance record (band actuals, constraint realization, engine, seed, draw
provenance). ``POST /loft/sessions`` writes these when ``persist_records`` is
set; the Sessions module will persist unconditionally per administration.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONColumn, PkUuidMixin, TimestampMixin


class LoftSessionRecordRow(PkUuidMixin, TimestampMixin, Base):
    __tablename__ = "loft_session_record"

    blueprint_id: Mapped[str] = mapped_column(
        ForeignKey("blueprint.id", ondelete="CASCADE"), index=True
    )
    pool_id: Mapped[str] = mapped_column()
    engine: Mapped[str] = mapped_column()
    seed: Mapped[int] = mapped_column()
    session_index: Mapped[int] = mapped_column(default=0)
    item_ids: Mapped[list[str]] = mapped_column(JSONColumn)
    #: the §4.4 conformance record, verbatim
    record: Mapped[dict] = mapped_column(JSONColumn)
