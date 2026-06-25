"""Schemas for the form-lifecycle governance layer + the form-QA report."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# --- lifecycle ---------------------------------------------------------------
class TransitionRequest(BaseModel):
    """A requested lifecycle transition. ``actor``/``actor_role`` are the *claimed*
    identity (recorded; not yet authorization-checked — role hook is a stub)."""

    action: str
    actor: str = "anonymous"
    actor_role: str | None = None
    comment: str | None = None


class ReviewEvent(BaseModel):
    id: str
    action: str
    from_state: str
    to_state: str
    actor: str
    actor_role: str | None
    comment: str | None
    created_at: datetime


class FormLifecycle(BaseModel):
    form_id: str
    state: str
    frozen: bool
    available_actions: list[str]
    events: list[ReviewEvent]


# --- form-QA report ----------------------------------------------------------
class AnswerKeyEntry(BaseModel):
    position: int
    item_id: str
    answer_key: str | None


class KeyBalance(BaseModel):
    counts: dict[str, int]
    n: int
    imbalanced: bool
    note: str


class CoverageRow(BaseModel):
    label: str
    count: int
    minimum: int | None
    maximum: int | None
    satisfied: bool


class QAPsychometricPoint(BaseModel):
    theta: float
    information: float
    se: float | None  # 1/sqrt(I); None when I == 0
    tcc: float  # expected raw score Σ Pᵢ(θ)


class TIFActualTarget(BaseModel):
    theta: float
    target: float
    actual: float


class FormQAReport(BaseModel):
    form_id: str
    lifecycle_state: str
    n_items: int
    metric: str = "logistic-D1-slope-intercept"
    answer_key: list[AnswerKeyEntry]
    key_balance: KeyBalance
    coverage: list[CoverageRow]
    #: SE(θ)=1/√I(θ) + TCC(θ)=Σ Pᵢ(θ) + information across the θ grid
    curve: list[QAPsychometricPoint]
    marginal_reliability: float = Field(ge=0.0, le=1.0)
    tif_actual_vs_target: list[TIFActualTarget]
