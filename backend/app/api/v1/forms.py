"""Form preview endpoint (plan §9: ``/api/v1/forms``).

Returns the assembled item order plus the actual-vs-target TIF, point by point —
the data behind the form-preview plot (plan §10).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.schemas.blueprint import Blueprint
from app.schemas.responses import FormRead, TIFPoint

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
