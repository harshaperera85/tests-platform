"""Form preview endpoint (plan §9: ``/api/v1/forms``).

Returns the assembled item order plus the actual-vs-target TIF, point by point —
the data behind the form-preview plot (plan §10).
"""

from __future__ import annotations

import urllib.error

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.assembly.ata_model import INFO_SCALE
from app.assembly.blueprint_compiler import compile_blueprint
from app.assembly.oracles import r_oracle
from app.core.config import settings
from app.core.db import get_db
from app.models.assembly_job import AssemblyJobRow
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics import pools
from app.psychometrics.information import test_information
from app.schemas.blueprint import Blueprint
from app.schemas.governance import (
    FormLifecycle,
    FormQAReport,
    ReviewEvent,
    TransitionRequest,
)
from app.schemas.responses import (
    FormRead,
    SimulationRead,
    SimulationStepRead,
    TIFCurve,
    TIFCurvePoint,
    TIFPoint,
)
from app.schemas.validation import (
    CrossValComparison,
    CrossValidationResult,
    CrossValOracle,
    CrossValSide,
)
from app.services import form_lifecycle, form_qa
from app.simulation import simulate_linear

router = APIRouter(prefix="/forms", tags=["forms"])


def _lifecycle_read(db: Session, form: FormRow) -> FormLifecycle:
    return FormLifecycle(
        form_id=form.id,
        state=form.lifecycle_state,
        frozen=form.lifecycle_state in form_lifecycle.FROZEN_STATES,
        available_actions=form_lifecycle.available_actions(form.lifecycle_state),
        events=[
            ReviewEvent(
                id=e.id,
                action=e.action,
                from_state=e.from_state,
                to_state=e.to_state,
                actor=e.actor,
                actor_role=e.actor_role,
                comment=e.comment,
                created_at=e.created_at,
            )
            for e in form_lifecycle.review_events(db, form.id)
        ],
    )


@router.get("/{form_id}/lifecycle", response_model=FormLifecycle)
def get_form_lifecycle(form_id: str, db: Session = Depends(get_db)) -> FormLifecycle:
    row = db.get(FormRow, form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="form not found")
    return _lifecycle_read(db, row)


@router.post("/{form_id}/transition", response_model=FormLifecycle)
def transition_form(
    form_id: str, payload: TransitionRequest, db: Session = Depends(get_db)
) -> FormLifecycle:
    """Move a form through the review/approve/publish lifecycle (records sign-off)."""
    row = db.get(FormRow, form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="form not found")
    try:
        form_lifecycle.apply_transition(
            db,
            row,
            payload.action,
            actor=payload.actor,
            actor_role=payload.actor_role,
            comment=payload.comment,
        )
    except form_lifecycle.LifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _lifecycle_read(db, row)


@router.get("/{form_id}/qa-report", response_model=FormQAReport)
def get_form_qa_report(form_id: str, db: Session = Depends(get_db)) -> FormQAReport:
    """Server-side form-QA report (answer key, key balance, coverage, SE/TCC, TIF)."""
    row = db.get(FormRow, form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="form not found")
    return form_qa.build_qa_report(db, row)


def _unsupported(
    ortools: CrossValSide, package: str, detail: str
) -> CrossValidationResult:
    return CrossValidationResult(
        status="unsupported",
        package=package,
        detail=detail,
        ortools=ortools,
        oracle=CrossValOracle(status="skipped"),
    )


@router.post("/{form_id}/cross-validate", response_model=CrossValidationResult)
def cross_validate_form(
    form_id: str, db: Session = Depends(get_db)
) -> CrossValidationResult:
    """Validate an assembled form against the eatATA R oracle (read-only).

    Recompiles the form's blueprint+pool to the same canonical D=1 problem, solves
    it with eatATA via the oracle-r service, and compares to the stored OR-Tools
    result. Never builds a deliverable form. Scope: single-form unweighted minimax
    (the eatATA bridge's objective).
    """
    row = db.get(FormRow, form_id)
    if row is None:
        raise HTTPException(status_code=404, detail="form not found")
    bp_row = db.get(BlueprintRow, row.blueprint_id)
    if bp_row is None:  # pragma: no cover - FK guarantees presence
        raise HTTPException(status_code=404, detail="blueprint not found")

    blueprint = Blueprint.model_validate(bp_row.spec)
    job = db.get(AssemblyJobRow, row.assembly_job_id)
    ortools_obj = (job.result or {}).get("objective_value") if job else None
    ortools = CrossValSide(item_ids=list(row.item_ids), objective_value=ortools_obj)
    package = "eatATA"

    # Scope guards: the eatATA bridge solves single-form, unweighted minimax.
    tgt = blueprint.statistical_target
    if blueprint.num_forms != 1:
        return _unsupported(ortools, package, "cross-validation is single-form only")
    if tgt.method != "minimax":
        return _unsupported(ortools, package, "oracle bridge validates minimax only")
    if any(w != 1.0 for w in tgt.resolved_weights):
        return _unsupported(
            ortools, package, "oracle bridge validates unweighted minimax only"
        )

    problem = compile_blueprint(blueprint, pools.load_pool_by_id(row.pool_id))
    try:
        rr = r_oracle.run_oracle_http(
            problem, base_url=settings.oracle_r_url, package=package
        )
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return CrossValidationResult(
            status="oracle_unavailable",
            package=package,
            detail=f"oracle-r service unreachable: {exc}",
            ortools=ortools,
            oracle=CrossValOracle(status="unavailable"),
        )

    oracle = CrossValOracle(
        status=rr.status,
        item_ids=rr.item_ids,
        objective_value=rr.objective_value,
        solver=rr.solver,
        solve_time_s=rr.solve_time_s,
    )
    if rr.status not in ("optimal", "feasible") or rr.item_ids is None:
        return CrossValidationResult(
            status="error",
            package=package,
            detail="oracle did not return a feasible solution",
            ortools=ortools,
            oracle=oracle,
        )

    ot_set, or_set = set(row.item_ids), set(rr.item_ids)
    union = ot_set | or_set
    # Objective tolerance from integer info-scaling: the engine rounds each item's
    # info to 1/INFO_SCALE before solving, so the accumulated miss on a TIF
    # *deviation* over L items is bounded by ~(L+1)/INFO_SCALE (eatATA solves the
    # unrounded LP). Matches the CI parity gate's tolerance.
    tolerance = (problem.length + 1) / INFO_SCALE
    obj_diff = (
        abs(ortools_obj - rr.objective_value)
        if ortools_obj is not None and rr.objective_value is not None
        else None
    )
    comparison = CrossValComparison(
        selection_match=ot_set == or_set,
        only_in_ortools=sorted(ot_set - or_set),
        only_in_oracle=sorted(or_set - ot_set),
        jaccard=(len(ot_set & or_set) / len(union)) if union else 1.0,
        objective_abs_diff=obj_diff,
        objective_within_tolerance=(obj_diff <= tolerance)
        if obj_diff is not None
        else None,
        tolerance=tolerance,
        tolerance_basis="(length + 1) / INFO_SCALE",
        constraints_satisfied=rr.status in ("optimal", "feasible"),
    )
    return CrossValidationResult(
        status="ok",
        package=package,
        ortools=ortools,
        oracle=oracle,
        comparison=comparison,
    )


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
        lifecycle_state=row.lifecycle_state,
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
