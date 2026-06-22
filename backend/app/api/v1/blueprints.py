"""Blueprint CRUD endpoints (plan §9: ``/api/v1/blueprints``)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.blueprint import BlueprintRow
from app.schemas.blueprint import Blueprint
from app.schemas.responses import BlueprintRead

router = APIRouter(prefix="/blueprints", tags=["blueprints"])


def _to_read(row: BlueprintRow) -> BlueprintRead:
    return BlueprintRead(
        id=row.id,
        name=row.name,
        length=row.length,
        num_forms=row.num_forms,
        created_at=row.created_at,
        blueprint=Blueprint.model_validate(row.spec),
    )


@router.post("", response_model=BlueprintRead, status_code=status.HTTP_201_CREATED)
def create_blueprint(
    blueprint: Blueprint, db: Session = Depends(get_db)
) -> BlueprintRead:
    row = BlueprintRow(
        name=blueprint.name,
        length=blueprint.length,
        num_forms=blueprint.num_forms,
        spec=blueprint.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_read(row)


@router.get("/{blueprint_id}", response_model=BlueprintRead)
def get_blueprint(blueprint_id: str, db: Session = Depends(get_db)) -> BlueprintRead:
    row = db.get(BlueprintRow, blueprint_id)
    if row is None:
        raise HTTPException(status_code=404, detail="blueprint not found")
    return _to_read(row)
