"""``item_usage_event`` table — append-only longitudinal item-exposure history.

One row per (item, form, context): records that an item was included in a form, and
in what lifecycle ``context``. Cumulative exposure across assembly/administration
events over time is derived by aggregating these rows.

Distinct from the within-batch exposure controls (overlap / max-use / rate), which
govern a *single* multi-form assembly: this persists usage *across* assemblies and
feeds back into eligibility. ``context``:
- ``published`` — the form reached the published lifecycle state (real exposure;
  the default "what counts").
- ``assembled`` — the item was placed in an assembled (draft) form (tracked
  separately; does not count toward eligibility unless explicitly configured).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import PkUuidMixin, TimestampMixin


class ItemUsageEventRow(PkUuidMixin, TimestampMixin, Base):
    __tablename__ = "item_usage_event"

    item_id: Mapped[str] = mapped_column(index=True)
    form_id: Mapped[str] = mapped_column(
        ForeignKey("form.id", ondelete="CASCADE"), index=True
    )
    test_id: Mapped[str | None] = mapped_column(nullable=True, index=True)
    pool_id: Mapped[str] = mapped_column(index=True)
    context: Mapped[str] = mapped_column(index=True)  # published | assembled
