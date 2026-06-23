"""Dry-run preview endpoint (plan §9 ``/api/v1/preview``).

A **thin** HTTP surface over the registered ``LinearStrategy``: it resolves the
strategy from the registry, calls the contract methods
(``initialize``/``next_action``/``record_response``/``is_complete``/``score``),
and serializes the result. It contains **no** sequencing or scoring logic of its
own — that all lives in the strategy (CLAUDE.md golden rule 1). The server holds no
session state; the JSON-serializable ``SessionState`` round-trips with the client.

This is additive API surface, not an engine-logic change — the strategy, engine
core, registry, and contract are untouched.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.engine import registry
from app.engine.contract import AdministrationStrategy, ScoreResult
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics.bank import load_default_pool
from app.schemas.blueprint import Blueprint
from app.schemas.preview import (
    PreviewRespondRequest,
    PreviewScoreRequest,
    PreviewStartRequest,
    PreviewStep,
)
from app.schemas.test_config import LinearConfig

router = APIRouter(prefix="/preview", tags=["preview"])


def _linear() -> AdministrationStrategy:
    return registry.get_strategy("linear")


def _step(strategy: AdministrationStrategy, state: Any) -> PreviewStep:
    """Serialize the current step. Only calls contract methods — no logic here."""
    return PreviewStep(
        state=state,
        next_action=strategy.next_action(state),
        termination=strategy.is_complete(state),
    )


@router.post("/start", response_model=PreviewStep)
def start_preview(
    payload: PreviewStartRequest, db: Session = Depends(get_db)
) -> PreviewStep:
    strategy = _linear()
    context: dict[str, Any] = {"session_id": payload.session_id or "preview-session"}

    if payload.form_id:
        form = db.get(FormRow, payload.form_id)
        if form is None:
            raise HTTPException(status_code=404, detail="form not found")
        context["form_item_ids"] = form.item_ids
    elif payload.blueprint_id:
        bp = db.get(BlueprintRow, payload.blueprint_id)
        if bp is None:
            raise HTTPException(status_code=404, detail="blueprint not found")
        context["blueprint"] = Blueprint.model_validate(bp.spec)
        context["assembly_strategy"] = payload.assembly_strategy
    else:
        raise HTTPException(
            status_code=422, detail="provide either blueprint_id or form_id"
        )

    state = strategy.initialize(LinearConfig(), load_default_pool(), context)
    return _step(strategy, state)


@router.post("/respond", response_model=PreviewStep)
def respond_preview(payload: PreviewRespondRequest) -> PreviewStep:
    strategy = _linear()
    new_state = strategy.record_response(
        payload.state, {"item_id": payload.item_id, "correct": payload.correct}
    )
    return _step(strategy, new_state)


@router.post("/score", response_model=ScoreResult)
def score_preview(payload: PreviewScoreRequest) -> ScoreResult:
    return _linear().score(payload.state)
