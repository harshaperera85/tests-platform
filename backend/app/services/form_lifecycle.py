"""Form lifecycle: the cross-model review → approve → publish state machine.

Model-agnostic governance over the assembled **form** (the deliverable Sessions will
administer) — NOT linear-specific; CAT/MST forms flow through the identical machine.
The engine core/contract/registry are untouched: this is a layer over the form
resource.

States::

    draft → content_review → psychometric_review → approved → published

with ``return_to_draft`` (reject, comment required) from either review gate, and
``withdraw`` (unpublish) from published back to draft. Only valid transitions are
allowed; anything else raises :class:`LifecycleError`.

Each forward gate declares a **required role** (content_reviewer / psychometrician /
publisher). Authorization is routed through one function,
:func:`authorize_transition`, which is currently a **deliberate permissive stub** —
it records the *claimed* actor/role but never denies. Real AuthN/AuthZ wires in at
that single point once it is decided (see CLAUDE.md / docs/security.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.form import FormRow
from app.models.form_review_event import FormReviewEventRow
from app.services import audit

DRAFT = "draft"
STATES = (
    DRAFT,
    "content_review",
    "psychometric_review",
    "approved",
    "published",
)
#: states in which the form is frozen from re-assembly / blueprint edits.
FROZEN_STATES = frozenset(STATES) - {DRAFT}


class LifecycleError(ValueError):
    """An invalid lifecycle transition (bad source state or missing comment)."""


@dataclass(frozen=True)
class Transition:
    from_states: tuple[str, ...]
    to_state: str
    required_role: str | None  # the gate's role (recorded; not yet enforced)
    comment_required: bool = False


TRANSITIONS: dict[str, Transition] = {
    "submit_for_review": Transition((DRAFT,), "content_review", None),
    "approve_content": Transition(
        ("content_review",), "psychometric_review", "content_reviewer"
    ),
    "approve_psychometric": Transition(
        ("psychometric_review",), "approved", "psychometrician"
    ),
    "publish": Transition(("approved",), "published", "publisher"),
    "return_to_draft": Transition(
        ("content_review", "psychometric_review"), DRAFT, None, comment_required=True
    ),
    "withdraw": Transition(("published",), DRAFT, "publisher"),
}


def available_actions(state: str) -> list[str]:
    """Transition actions valid from ``state`` (drives the UI's gate buttons)."""
    return [a for a, t in TRANSITIONS.items() if state in t.from_states]


def authorize_transition(
    action: str, *, actor: str, actor_role: str | None, required_role: str | None
) -> None:
    """ROLE HOOK — **deliberate permissive stub**.

    Records the claimed ``actor``/``actor_role`` (via the caller) but performs **no**
    authorization check: any actor may perform any transition for now. This is the
    single chokepoint where real role enforcement is added once AuthN/AuthZ is
    decided; until then it never raises.
    """
    return None


def apply_transition(
    db: Session,
    form: FormRow,
    action: str,
    *,
    actor: str = "anonymous",
    actor_role: str | None = None,
    comment: str | None = None,
) -> FormRow:
    """Validate + perform a lifecycle transition, recording the sign-off."""
    t = TRANSITIONS.get(action)
    if t is None:
        raise LifecycleError(f"unknown transition '{action}'")
    if form.lifecycle_state not in t.from_states:
        raise LifecycleError(
            f"cannot '{action}' from state '{form.lifecycle_state}'"
        )
    if t.comment_required and not (comment and comment.strip()):
        raise LifecycleError(f"'{action}' requires a comment")

    authorize_transition(
        action, actor=actor, actor_role=actor_role, required_role=t.required_role
    )

    from_state = form.lifecycle_state
    form.lifecycle_state = t.to_state
    db.add(
        FormReviewEventRow(
            form_id=form.id,
            action=action,
            from_state=from_state,
            to_state=t.to_state,
            actor=actor or "anonymous",
            actor_role=actor_role,
            comment=comment,
        )
    )
    db.commit()
    db.refresh(form)
    audit.record(
        db,
        action=f"form.{action}",
        entity_type="form",
        entity_id=form.id,
        detail={
            "from": from_state,
            "to": t.to_state,
            "actor": actor,
            "actor_role": actor_role,
            "comment": comment,
        },
    )
    return form


def review_events(db: Session, form_id: str) -> list[FormReviewEventRow]:
    """The sign-off trail for a form, oldest first."""
    return list(
        db.scalars(
            select(FormReviewEventRow)
            .where(FormReviewEventRow.form_id == form_id)
            .order_by(FormReviewEventRow.created_at)
        )
    )


def test_has_frozen_form(db: Session, test_id: str) -> bool:
    """True if any form of ``test_id`` has left draft (freezes re-assembly/edits)."""
    states = db.scalars(
        select(FormRow.lifecycle_state).where(FormRow.test_id == test_id)
    ).all()
    return any(s in FROZEN_STATES for s in states)
