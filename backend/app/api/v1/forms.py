"""Form preview endpoint (plan §9: ``/api/v1/forms``).

Returns the assembled item order plus the actual-vs-target TIF, point by point —
the data behind the form-preview plot (plan §10).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics import pools
from app.psychometrics.information import test_information
from app.schemas.blueprint import Blueprint
from app.schemas.responses import (
    FormRead,
    SimulationRead,
    SimulationStepRead,
    TIFCurve,
    TIFCurvePoint,
    TIFPoint,
)
from app.simulation import simulate_linear

router = APIRouter(prefix="/forms", tags=["forms"])


@router.get("/{form_id}", response_model=FormRead)
def get_form(form_id: str, db: Session = Depends(get_db)) -> FormRead:
    row = db.get(FormRow, form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="form not found")

    bp_row = db.get(BlueprintRow, row.blueprint_id)
    if bp_row is None:  # pragma: no cover - FK guarantees presence
        raise HTTPException(status_code=404, detail="blueprint not found")
    target = Blueprint.model_validate(bp_row.spec).statistical_target

    tif = [
        TIFPoint(
            theta=theta,
            target=tgt,
            actual=actual,
            gap=actual - tgt,
        )
        for theta, tgt, actual in zip(
            target.theta_points, target.target_info, row.tif_actual, strict=True
        )
    ]
    return FormRead(
        id=row.id,
        blueprint_id=row.blueprint_id,
        assembly_job_id=row.assembly_job_id,
        form_index=row.form_index,
        status=row.status,
        item_ids=row.item_ids,
        created_at=row.created_at,
        tif=tif,
    )


@router.get("/{form_id}/tif-curve", response_model=TIFCurve)
def get_form_tif_curve(
    form_id: str,
    theta_min: float = Query(default=-3.0),
    theta_max: float = Query(default=3.0),
    n: int = Query(default=61, ge=2, le=400),
    db: Session = Depends(get_db),
) -> TIFCurve:
    """Dense actual TIF over a theta grid (computed via the canonical metric).

    Lets the UI draw a smooth actual curve against the discrete blueprint target.
    """
    row = db.get(FormRow, form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="form not found")
    bp_row = db.get(BlueprintRow, row.blueprint_id)
    if bp_row is None:  # pragma: no cover - FK guarantees presence
        raise HTTPException(status_code=404, detail="blueprint not found")
    target = Blueprint.model_validate(bp_row.spec).statistical_target

    pool = pools.load_pool_by_id(row.pool_id)
    items = pool.subset(row.item_ids)
    step = (theta_max - theta_min) / (n - 1)
    curve = [
        TIFCurvePoint(
            theta=theta_min + i * step,
            actual=test_information(items, theta_min + i * step),
        )
        for i in range(n)
    ]
    return TIFCurve(
        theta_points=list(target.theta_points),
        target_info=list(target.target_info),
        tolerance=target.tolerance,
        method=target.method,
        curve=curve,
    )


@router.get("/{form_id}/simulate", response_model=SimulationRead)
def simulate_form(
    form_id: str,
    theta: float = Query(default=0.0, description="examinee's true theta"),
    seed: int = Query(default=0),
    db: Session = Depends(get_db),
) -> SimulationRead:
    """Simulate an examinee at ``theta`` walking this form (real engine + 2PL)."""
    row = db.get(FormRow, form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="form not found")

    pool = pools.load_pool_by_id(row.pool_id)
    result = simulate_linear(pool, row.item_ids, theta, seed=seed)
    return SimulationRead(
        form_id=form_id,
        true_theta=result.true_theta,
        seed=result.seed,
        n_items=result.n_items,
        final_theta=result.final_theta,
        final_standard_error=result.final_standard_error,
        trace=[
            SimulationStepRead(
                position=s.position,
                item_id=s.item_id,
                prob_correct=s.prob_correct,
                response=s.response,
                theta=s.theta,
                standard_error=s.standard_error,
            )
            for s in result.trace
        ],
    )
