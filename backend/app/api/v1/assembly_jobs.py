"""Assembly-job endpoints (plan §9: ``/api/v1/assembly-jobs``).

POST assembles form(s) from a stored blueprint via the owned OR-Tools engine and
persists the job + resulting forms. v1 solves synchronously; the row shape is ready
for the long-solve-as-RQ-job path (plan §6/§7) without an API change.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.assembly import assemble
from app.core.db import get_db
from app.models.assembly_job import AssemblyJobRow
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics import pools
from app.schemas.blueprint import Blueprint
from app.schemas.responses import AssemblyJobCreate, AssemblyJobRead

router = APIRouter(prefix="/assembly-jobs", tags=["assembly-jobs"])


def _to_read(job: AssemblyJobRow, form_ids: list[str]) -> AssemblyJobRead:
    result = job.result or {}
    return AssemblyJobRead(
        id=job.id,
        blueprint_id=job.blueprint_id,
        pool_id=job.pool_id,
        strategy=job.strategy,
        status=job.status,
        method=result.get("method"),
        objective_value=result.get("objective_value"),
        theta_points=result.get("theta_points", []),
        target_info=result.get("target_info", []),
        warnings=result.get("warnings", []),
        form_ids=form_ids,
        created_at=job.created_at,
    )


@router.post("", response_model=AssemblyJobRead, status_code=status.HTTP_201_CREATED)
def create_assembly_job(
    payload: AssemblyJobCreate, db: Session = Depends(get_db)
) -> AssemblyJobRead:
    bp_row = db.get(BlueprintRow, payload.blueprint_id)
    if bp_row is None:
        raise HTTPException(status_code=404, detail="blueprint not found")
    if not pools.is_known(payload.pool_id):
        raise HTTPException(
            status_code=404, detail=f"unknown pool_id {payload.pool_id!r}"
        )

    blueprint = Blueprint.model_validate(bp_row.spec)
    pool = pools.load_pool_by_id(payload.pool_id)
    result = assemble(
        blueprint,
        pool,
        strategy=payload.strategy,
        time_limit_s=payload.time_limit_s,
        seed=payload.seed,
    )

    job = AssemblyJobRow(
        blueprint_id=bp_row.id,
        pool_id=payload.pool_id,
        strategy=payload.strategy,
        status=result.status,
        params={"seed": payload.seed, "time_limit_s": payload.time_limit_s},
        result={
            "method": result.method,
            "objective_value": result.objective_value,
            "theta_points": result.theta_points,
            "target_info": result.target_info,
            "warnings": result.warnings,
        },
    )
    db.add(job)
    db.flush()  # assign job.id before forms reference it

    form_ids: list[str] = []
    for idx, form in enumerate(result.forms):
        row = FormRow(
            blueprint_id=bp_row.id,
            assembly_job_id=job.id,
            form_index=idx,
            status="draft",
            pool_id=payload.pool_id,
            item_ids=form.item_ids,
            tif_actual=form.tif_actual,
        )
        db.add(row)
        db.flush()
        form_ids.append(row.id)

    db.commit()
    db.refresh(job)
    return _to_read(job, form_ids)


@router.get("/{job_id}", response_model=AssemblyJobRead)
def get_assembly_job(job_id: str, db: Session = Depends(get_db)) -> AssemblyJobRead:
    job = db.get(AssemblyJobRow, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="assembly job not found")
    form_ids = [
        r.id
        for r in db.query(FormRow)
        .filter(FormRow.assembly_job_id == job_id)
        .order_by(FormRow.form_index)
        .all()
    ]
    return _to_read(job, form_ids)
