"""``tests`` resource — the authoring entity (plan §8/§9).

CRUD + list + draft persistence + assemble (snapshots the draft and runs the owned
engine) + form history + status workflow (lock/unlock/duplicate). Additive API;
no engine logic. Replaces the frontend's client-side test registry.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.models.test import TestRow
from app.psychometrics import pools
from app.schemas.blueprint import Blueprint
from app.schemas.responses import AssemblyJobRead
from app.schemas.tests import (
    FormSummary,
    TestAssembleRequest,
    TestCreate,
    TestRead,
    TestSummary,
    TestUpdate,
)
from app.services.assembly_run import run_assembly

router = APIRouter(prefix="/tests", tags=["tests"])


def _form_count(db: Session, test_id: str) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(FormRow).where(FormRow.test_id == test_id)
        )
        or 0
    )


def _blueprint_of(test: TestRow) -> Blueprint | None:
    return (
        Blueprint.model_validate(test.blueprint_spec) if test.blueprint_spec else None
    )


def _to_read(test: TestRow, form_count: int) -> TestRead:
    return TestRead(
        id=test.id,
        name=test.name,
        administration_model=test.administration_model,
        status=test.status,
        pool_id=test.pool_id,
        version=test.version,
        blueprint=_blueprint_of(test),
        form_count=form_count,
        created_at=test.created_at,
        updated_at=test.updated_at,
    )


def _get_or_404(db: Session, test_id: str) -> TestRow:
    test = db.get(TestRow, test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="test not found")
    return test


@router.post("", response_model=TestRead, status_code=status.HTTP_201_CREATED)
def create_test(payload: TestCreate, db: Session = Depends(get_db)) -> TestRead:
    if not pools.is_known(payload.pool_id):
        raise HTTPException(
            status_code=404, detail=f"unknown pool_id {payload.pool_id!r}"
        )
    test = TestRow(
        name=payload.name,
        administration_model=payload.administration_model,
        pool_id=payload.pool_id,
        blueprint_spec=payload.blueprint.model_dump(mode="json")
        if payload.blueprint
        else None,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return _to_read(test, 0)


@router.get("", response_model=list[TestSummary])
def list_tests(db: Session = Depends(get_db)) -> list[TestSummary]:
    tests = db.query(TestRow).order_by(TestRow.updated_at.desc()).all()
    counts: dict[str, int] = {
        tid: int(n)
        for tid, n in db.execute(
            select(FormRow.test_id, func.count())
            .where(FormRow.test_id.is_not(None))
            .group_by(FormRow.test_id)
        ).all()
        if tid is not None
    }
    return [
        TestSummary(
            id=t.id,
            name=t.name,
            administration_model=t.administration_model,
            status=t.status,
            pool_id=t.pool_id,
            version=t.version,
            form_count=int(counts.get(t.id, 0)),
            has_blueprint=t.blueprint_spec is not None,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tests
    ]


@router.get("/{test_id}", response_model=TestRead)
def get_test(test_id: str, db: Session = Depends(get_db)) -> TestRead:
    test = _get_or_404(db, test_id)
    return _to_read(test, _form_count(db, test_id))


@router.patch("/{test_id}", response_model=TestRead)
def update_test(
    test_id: str, payload: TestUpdate, db: Session = Depends(get_db)
) -> TestRead:
    test = _get_or_404(db, test_id)
    if test.status == "locked":
        raise HTTPException(status_code=409, detail="test is locked; unlock to edit")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        test.name = data["name"]
    if "pool_id" in data and data["pool_id"] is not None:
        if not pools.is_known(data["pool_id"]):
            raise HTTPException(status_code=404, detail="unknown pool_id")
        test.pool_id = data["pool_id"]
    if "blueprint" in data and payload.blueprint is not None:
        test.blueprint_spec = payload.blueprint.model_dump(mode="json")
    test.version += 1
    db.commit()
    db.refresh(test)
    return _to_read(test, _form_count(db, test_id))


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test(test_id: str, db: Session = Depends(get_db)) -> None:
    test = _get_or_404(db, test_id)
    db.delete(test)
    db.commit()


@router.post(
    "/{test_id}/assemble",
    response_model=AssemblyJobRead,
    status_code=status.HTTP_201_CREATED,
)
def assemble_test(
    test_id: str, payload: TestAssembleRequest, db: Session = Depends(get_db)
) -> AssemblyJobRead:
    test = _get_or_404(db, test_id)
    if test.status == "locked":
        raise HTTPException(
            status_code=409, detail="test is locked; unlock to assemble"
        )
    if test.blueprint_spec is None:
        raise HTTPException(status_code=422, detail="test has no blueprint to assemble")

    bp = Blueprint.model_validate(test.blueprint_spec)
    bp_row = BlueprintRow(
        name=bp.name,
        length=bp.length,
        num_forms=bp.num_forms,
        spec=test.blueprint_spec,
    )
    db.add(bp_row)
    db.flush()

    job, forms = run_assembly(
        db,
        blueprint_row=bp_row,
        pool_id=test.pool_id,
        strategy=payload.strategy,
        seed=payload.seed,
        time_limit_s=payload.time_limit_s,
        test_id=test.id,
    )
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
        form_ids=[f.id for f in forms],
        created_at=job.created_at,
    )


@router.get("/{test_id}/forms", response_model=list[FormSummary])
def list_test_forms(test_id: str, db: Session = Depends(get_db)) -> list[FormSummary]:
    _get_or_404(db, test_id)
    rows = (
        db.query(FormRow)
        .filter(FormRow.test_id == test_id)
        .order_by(FormRow.created_at.desc(), FormRow.form_index)
        .all()
    )
    return [
        FormSummary(
            id=r.id,
            assembly_job_id=r.assembly_job_id,
            blueprint_id=r.blueprint_id,
            pool_id=r.pool_id,
            form_index=r.form_index,
            status=r.status,
            n_items=len(r.item_ids),
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/{test_id}/lock", response_model=TestRead)
def lock_test(test_id: str, db: Session = Depends(get_db)) -> TestRead:
    test = _get_or_404(db, test_id)
    if _form_count(db, test_id) == 0:
        raise HTTPException(status_code=409, detail="assemble a form before locking")
    test.status = "locked"
    db.commit()
    db.refresh(test)
    return _to_read(test, _form_count(db, test_id))


@router.post("/{test_id}/unlock", response_model=TestRead)
def unlock_test(test_id: str, db: Session = Depends(get_db)) -> TestRead:
    test = _get_or_404(db, test_id)
    test.status = "draft"
    db.commit()
    db.refresh(test)
    return _to_read(test, _form_count(db, test_id))


@router.post(
    "/{test_id}/duplicate", response_model=TestRead, status_code=status.HTTP_201_CREATED
)
def duplicate_test(test_id: str, db: Session = Depends(get_db)) -> TestRead:
    src = _get_or_404(db, test_id)
    copy = TestRow(
        name=f"{src.name} (copy)",
        administration_model=src.administration_model,
        pool_id=src.pool_id,
        blueprint_spec=src.blueprint_spec,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return _to_read(copy, 0)
