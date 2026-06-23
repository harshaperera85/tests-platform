"""Assembly job lifecycle: create (queued) → dispatch → execute (solve + persist).

``dispatch`` enqueues the solve to RQ when ``settings.assembly_async`` is set (a
worker runs ``execute_job``); otherwise it runs inline. ``execute_job`` is the
single solve path shared by the worker and the inline fallback. Pure orchestration
around the engine — no engine logic here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.assembly import assemble
from app.core.config import settings
from app.core.redis import get_queue
from app.models.assembly_job import AssemblyJobRow
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics import pools
from app.schemas.blueprint import Blueprint

_TERMINAL = {"optimal", "feasible", "infeasible", "error"}


def create_job(
    db: Session,
    *,
    blueprint_row: BlueprintRow,
    pool_id: str,
    strategy: str,
    seed: int,
    time_limit_s: float,
    test_id: str | None = None,
) -> AssemblyJobRow:
    """Persist a queued job (no forms yet)."""
    job = AssemblyJobRow(
        blueprint_id=blueprint_row.id,
        test_id=test_id,
        pool_id=pool_id,
        strategy=strategy,
        status="queued",
        params={"seed": seed, "time_limit_s": time_limit_s},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def execute_job(db: Session, job: AssemblyJobRow) -> AssemblyJobRow:
    """Run the solve for a queued job and persist forms + terminal status."""
    if job.status in _TERMINAL:
        return job  # idempotent: already done
    job.status = "running"
    db.commit()

    bp_row = db.get(BlueprintRow, job.blueprint_id)
    if bp_row is None:  # pragma: no cover - FK guarantees presence
        job.status = "error"
        job.result = {"error": "blueprint missing"}
        db.commit()
        return job

    params = job.params or {}
    try:
        blueprint = Blueprint.model_validate(bp_row.spec)
        pool = pools.load_pool_by_id(job.pool_id)
        result = assemble(
            blueprint,
            pool,
            strategy=job.strategy,
            time_limit_s=float(params.get("time_limit_s", 10.0)),
            seed=int(params.get("seed", 0)),
        )
    except Exception as exc:  # noqa: BLE001 - record any solver/setup failure
        job.status = "error"
        job.result = {"error": str(exc)}
        db.commit()
        return job

    job.status = result.status
    job.result = {
        "method": result.method,
        "objective_value": result.objective_value,
        "theta_points": result.theta_points,
        "target_info": result.target_info,
        "warnings": result.warnings,
    }
    for idx, form in enumerate(result.forms):
        db.add(
            FormRow(
                blueprint_id=bp_row.id,
                assembly_job_id=job.id,
                test_id=job.test_id,
                form_index=idx,
                status="draft",
                pool_id=job.pool_id,
                item_ids=form.item_ids,
                tif_actual=form.tif_actual,
            )
        )
    db.commit()
    db.refresh(job)
    return job


def dispatch(db: Session, job: AssemblyJobRow) -> None:
    """Enqueue the solve (async) or run it inline (sync), per settings."""
    if settings.assembly_async:
        from app.workers.tasks import execute_assembly_job

        get_queue().enqueue(
            execute_assembly_job, job.id, job_timeout=settings.assembly_job_timeout_s
        )
    else:
        execute_job(db, job)
