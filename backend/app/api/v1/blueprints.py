"""Blueprint CRUD endpoints (plan §9: ``/api/v1/blueprints``)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.blueprint import BlueprintRow
from app.psychometrics import pools
from app.schemas.blueprint import Blueprint
from app.schemas.generator import (
    FeasibilityIssue,
    GenerateBlueprintRequest,
    GenerateBlueprintResponse,
)
from app.schemas.responses import BlueprintRead
from app.services import curricula
from app.services.blueprint_generator import check_feasibility, generate_blueprint

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


@router.post("/generate", response_model=GenerateBlueprintResponse)
def generate_blueprint_from_curriculum(
    req: GenerateBlueprintRequest,
) -> GenerateBlueprintResponse:
    """Curriculum→blueprint generator (BP-MODES-1 §6, rev. 2026-07-09).

    Consumes a curriculum manifest (inline, or by ``course_id`` from the catalog)
    and emits a blueprint for the requested §6.2 test type (unit_quiz /
    mid_course / end_of_course / cumulative_final) using §6.1 dimension-sum
    weights (median imputation, reported), largest-remainder rounding, authored
    cognitive profile, and per-binding TIF/cell rules. When ``pool_id`` is given
    the blueprint is validated against that pool's tag counts (the §6 gate). The
    blueprint is returned for review, not stored — persist via ``POST /blueprints``.
    """
    manifest = req.manifest
    if manifest is None:
        assert req.course_id is not None  # enforced by the request validator
        manifest = curricula.get_manifest(req.course_id)
        if manifest is None:
            raise HTTPException(
                status_code=404, detail=f"unknown course_id {req.course_id!r}"
            )
    try:
        blueprint, shares, imputed_fraction, warnings = generate_blueprint(
            req, manifest
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    checked, feasible = False, True
    issues: list[FeasibilityIssue] = []
    if req.pool_id is not None:
        if not pools.is_known(req.pool_id):
            raise HTTPException(
                status_code=404, detail=f"unknown pool_id {req.pool_id!r}"
            )
        feasible, issues, notes = check_feasibility(
            blueprint, pools.load_pool_by_id(req.pool_id)
        )
        warnings.extend(notes)
        checked = True

    return GenerateBlueprintResponse(
        blueprint=blueprint,
        shares=shares,
        imputed_fraction=imputed_fraction,
        feasibility_checked=checked,
        feasible=feasible,
        issues=issues,
        warnings=warnings,
    )


@router.get("/{blueprint_id}", response_model=BlueprintRead)
def get_blueprint(blueprint_id: str, db: Session = Depends(get_db)) -> BlueprintRead:
    row = db.get(BlueprintRow, blueprint_id)
    if row is None:
        raise HTTPException(status_code=404, detail="blueprint not found")
    return _to_read(row)
