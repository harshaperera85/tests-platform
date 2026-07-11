"""Wire schemas for the dry-run preview endpoint (plan §9 ``/api/v1/preview``).

The preview is **stateless on the server**: the JSON-serializable
``SessionState`` (engine contract) is the round-trip token. The client sends the
state it last received back with each call. This keeps the endpoint thin — it owns
no session storage and no sequencing/scoring logic; all of that stays in
``LinearStrategy`` (CLAUDE.md golden rule 1).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.engine.contract import NextAction, SessionState, TerminationDecision
from app.schemas.test_config import DeliveryOptions


class PreviewStartRequest(BaseModel):
    """Start a dry-run from a stored blueprint (assemble now) or a stored form."""

    blueprint_id: str | None = None
    form_id: str | None = None
    pool_id: str = "small_2pl"  # used when starting from a blueprint_id
    assembly_strategy: str = "mip"
    session_id: str | None = None
    #: G5 delivery options (order randomization / embedded pretest) — the
    #: preview walks exactly what a delivery session would present.
    delivery: DeliveryOptions = Field(default_factory=DeliveryOptions)


class PreviewRespondRequest(BaseModel):
    """Record one response against the carried-back session state."""

    state: SessionState
    item_id: str | None = None
    correct: int


class PreviewScoreRequest(BaseModel):
    """Score the carried-back session state."""

    state: SessionState


class PreviewStep(BaseModel):
    """One step of the walkthrough: the new state + what to do next.

    ``next_action.navigation`` carries the strategy's capabilities, so no separate
    capabilities call is needed.
    """

    state: SessionState
    next_action: NextAction
    termination: TerminationDecision
