"""Shared assembly execution: run the engine + persist job/forms.

Used by both ``POST /assembly-jobs`` (against an existing blueprint) and
``POST /tests/{id}/assemble`` (against a test's snapshotted draft). v1 solves
synchronously; this is the seam where a long solve moves to an RQ job (Tier 2)
without changing callers. Pure orchestration — no engine logic here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.assembly import assemble
from app.models.assembly_job import AssemblyJobRow
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics import pools
from app.schemas.blueprint import Blueprint


def run_assembly(
    db: Session,
    *,
    blueprint_row: BlueprintRow,
    pool_id: str,
    strategy: str,
    seed: int,
    time_limit_s: float,
    test_id: str | None = None,
) -> tuple[AssemblyJobRow, list[FormRow]]:
    """Assemble ``blueprint_row``'s spec on ``pool_id``; persist job + forms."""
    blueprint = Blueprint.model_validate(blueprint_row.spec)
    pool = pools.load_pool_by_id(pool_id)
    result = assemble(
        blueprint, pool, strategy=strategy, time_limit_s=time_limit_s, seed=seed
    )

    job = AssemblyJobRow(
        blueprint_id=blueprint_row.id,
        test_id=test_id,
        pool_id=pool_id,
        strategy=strategy,
        status=result.status,
        params={"seed": seed, "time_limit_s": time_limit_s},
        result={
            "method": result.method,
            "objective_value": result.objective_value,
            "theta_points": result.theta_points,
            "target_info": result.target_info,
            "warnings": result.warnings,
        },
    )
    db.add(job)
    db.flush()

    forms: list[FormRow] = []
    for idx, form in enumerate(result.forms):
        row = FormRow(
            blueprint_id=blueprint_row.id,
            assembly_job_id=job.id,
            test_id=test_id,
            form_index=idx,
            status="draft",
            pool_id=pool_id,
            item_ids=form.item_ids,
            tif_actual=form.tif_actual,
        )
        db.add(row)
        db.flush()
        forms.append(row)

    db.commit()
    db.refresh(job)
    return job, forms
