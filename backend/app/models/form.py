"""``form`` table — an assembled fixed-form (plan §8).

Holds the ordered item ids and the realized TIF (``tif_actual``); the preview
endpoint pairs ``tif_actual`` with the blueprint's target for the actual-vs-target
plot.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONColumn, PkUuidMixin, TimestampMixin


class FormRow(PkUuidMixin, TimestampMixin, Base):
    __tablename__ = "form"

    blueprint_id: Mapped[str] = mapped_column(
        ForeignKey("blueprint.id", ondelete="CASCADE"), index=True
    )
    assembly_job_id: Mapped[str] = mapped_column(
        ForeignKey("assembly_job.id", ondelete="CASCADE"), index=True
    )
    form_index: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(default="draft")  # draft/locked
    #: pool this form was assembled from — item_ids resolve against it
    pool_id: Mapped[str] = mapped_column(
        default="small_2pl", server_default="small_2pl"
    )
    item_ids: Mapped[list[str]] = mapped_column(JSONColumn)
    tif_actual: Mapped[list[float]] = mapped_column(JSONColumn)
