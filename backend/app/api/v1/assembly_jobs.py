"""Assembly-job endpoints (plan §9: ``/api/v1/assembly-jobs``).

POST assembles form(s) from a stored blueprint via the owned OR-Tools engine and
persists the job + resulting forms. v1 solves synchronously; the row shape is ready
for the long-solve-as-RQ-job path (plan §6/§7) without an API change.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.assembly_job import AssemblyJobRow
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics import pools
from app.schemas.responses import AssemblyJobCreate, AssemblyJobRead
from app.services.assembly_run import create_job, dispatch


def _form_ids(db: Session, job_id: str) -> list[str]:
    return [
        r.id
        for r in db.query(FormRow)
        .filter(FormRow.assembly_job_id == job_id)
        .order_by(FormRow.form_index)
        .all()
    ]


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
        error=result.get("error"),
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

    job = create_job(
        db,
        blueprint_row=bp_row,
        pool_id=payload.pool_id,
        strategy=payload.strategy,
        seed=payload.seed,
        time_limit_s=payload.time_limit_s,
    )
    dispatch(db, job)
    db.refresh(job)
    return _to_read(job, _form_ids(db, job.id))


@router.get("/{job_id}", response_model=AssemblyJobRead)
def get_assembly_job(job_id: str, db: Session = Depends(get_db)) -> AssemblyJobRead:
    job = db.get(AssemblyJobRow, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="assembly job not found")
    return _to_read(job, _form_ids(db, job_id))
