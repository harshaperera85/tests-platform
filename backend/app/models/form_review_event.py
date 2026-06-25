"""``form_review_event`` table — append-only sign-off trail for the form lifecycle.

One row per lifecycle transition: who moved the form (claimed actor + role), from
which state to which, when, with what comment. This provenance is the
defensibility-relevant core of the review → approve → publish workflow; it is
append-only and queryable (surfaced in the History tab). Linked to the global
``audit_event`` log, which also records each transition.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import PkUuidMixin, TimestampMixin


class FormReviewEventRow(PkUuidMixin, TimestampMixin, Base):
    __tablename__ = "form_review_event"

    form_id: Mapped[str] = mapped_column(
        ForeignKey("form.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column()  # submit_for_review, approve_content, ...
    from_state: Mapped[str] = mapped_column()
    to_state: Mapped[str] = mapped_column()
    #: claimed actor + role (recorded, NOT yet authorization-checked — see
    #: services/form_lifecycle.authorize_transition).
    actor: Mapped[str] = mapped_column(default="anonymous")
    actor_role: Mapped[str | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(nullable=True)
