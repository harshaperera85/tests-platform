"""Job robustness: a failing solve is recorded as 'error' with a message."""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from app.models.blueprint import BlueprintRow
from app.schemas.blueprint import Blueprint, TIFTarget
from app.services import assembly_run


def _bp() -> Blueprint:
    return Blueprint(
        name="err",
        length=5,
        statistical_target=TIFTarget(theta_points=[0], target_info=[3]),
    )


def test_execute_job_records_error(db_sessionmaker: sessionmaker) -> None:
    db = db_sessionmaker()
    try:
        bp = BlueprintRow(
            name="err", length=5, num_forms=1, spec=_bp().model_dump(mode="json")
        )
        db.add(bp)
        db.commit()
        # an unknown pool makes the solve raise; execute_job must capture it
        job = assembly_run.create_job(
            db,
            blueprint_row=bp,
            pool_id="does_not_exist",
            strategy="mip",
            seed=0,
            time_limit_s=5,
        )
        done = assembly_run.execute_job(db, job)
        assert done.status == "error"
        assert done.result and "error" in done.result
    finally:
        db.close()
