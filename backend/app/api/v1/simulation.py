"""``POST /simulations`` — the G1 measurement-simulation study endpoint.

Runs a shared simulee population through 1–4 design conditions on the
**in-process same-engine lane** (real assembly + real scoring; only the
examinee is simulated) and returns recovery / conditional / exposure /
paired-comparison statistics under a §4-format report block.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics import pools
from app.schemas.blueprint import Blueprint
from app.schemas.simulation import (
    LinearDesign,
    ReportBlock,
    ReportLane,
    SimulationRequest,
    SimulationStudyRead,
)
from app.simulation.harness import (
    compare_paired,
    requires_full_engine,
    run_condition,
    summarize,
)

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("", response_model=SimulationStudyRead)
def run_simulation_study(
    payload: SimulationRequest, db: Session = Depends(get_db)
) -> SimulationStudyRead:
    if not pools.is_known(payload.pool_id):
        raise HTTPException(
            status_code=404, detail=f"unknown pool_id {payload.pool_id!r}"
        )
    if pools.is_field_pool(payload.pool_id):
        raise HTTPException(
            status_code=422,
            detail=(
                "field-study pools cannot be simulated: their items are "
                "uncalibrated (no parameters to generate or score responses)"
            ),
        )
    pool = pools.load_pool_by_id(payload.pool_id)

    # resolve per-condition inputs up front (fail before any long run)
    resolved: list[tuple[Blueprint | None, list[str] | None]] = []
    for cond in payload.conditions:
        blueprint: Blueprint | None = None
        form_item_ids: list[str] | None = None
        design = cond.design
        bp_id = design.blueprint_id
        if bp_id is not None:
            bp_row = db.get(BlueprintRow, bp_id)
            if bp_row is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"condition {cond.name!r}: blueprint not found",
                )
            blueprint = Blueprint.model_validate(bp_row.spec)
        if isinstance(design, LinearDesign) and design.form_id is not None:
            form_row = db.get(FormRow, design.form_id)
            if form_row is None:
                raise HTTPException(
                    status_code=404, detail=f"condition {cond.name!r}: form not found"
                )
            if form_row.pool_id != payload.pool_id:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"condition {cond.name!r}: form was assembled from pool "
                        f"{form_row.pool_id!r}, not {payload.pool_id!r}"
                    ),
                )
            form_item_ids = list(form_row.item_ids)
        resolved.append((blueprint, form_item_ids))

    runs = []
    for cond, (blueprint, form_item_ids) in zip(
        payload.conditions, resolved, strict=True
    ):
        try:
            run = run_condition(
                cond,
                pool,
                blueprint=blueprint,
                form_item_ids=form_item_ids,
                population=payload.population,
                n_simulees=payload.n_simulees,
                replications=payload.replications,
                seed=payload.seed,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"condition {cond.name!r}: {exc}"
            ) from exc
        runs.append(run)

    results = [
        summarize(run, cond)
        for run, cond in zip(runs, payload.conditions, strict=True)
    ]
    comparisons = [
        compare_paired(
            payload.conditions[i].name, runs[i], payload.conditions[j].name, runs[j]
        )
        for i in range(len(runs))
        for j in range(i + 1, len(runs))
    ]

    first = runs[0].outcomes
    step = max(1, len(first) // 1000)
    scatter = [
        (round(o.true_theta, 4), round(o.est_theta, 4)) for o in first[::step]
    ]

    lanes = [
        ReportLane(
            lane="in_process_same_engine",
            coverage=(
                "assembly via production assemble()/assemble_loft_session() "
                "(same compiler/engines/masks/seeds); scoring via eap_estimate "
                "(the function the strategies' score() delegates to); ONLY the "
                "examinee is simulated (responses ~ Bernoulli(prob_correct)). "
                "Boundary predicate: "
                + "; ".join(
                    r for c in payload.conditions for r in requires_full_engine(c)
                )
            ),
        )
    ]
    report = ReportBlock(
        protocol="G1 measurement simulation (docs/loft_literature_review.md §2-G1)",
        date=datetime.now(UTC).isoformat(timespec="seconds"),
        engine="tests-platform linear/LOFT (in-process)",
        lanes=lanes,
        seeds={"global": payload.seed},
        n_per_condition=payload.n_simulees * payload.replications,
        inputs={
            "pool_id": payload.pool_id,
            "conditions": ", ".join(
                f"{c.name}={c.design.kind}" for c in payload.conditions
            ),
            "population": (
                f"{payload.population.distribution}"
                f"(mean={payload.population.mean}, sd={payload.population.sd})"
                if payload.population.distribution == "normal"
                else f"uniform({payload.population.low}, {payload.population.high})"
            ),
        },
        driver="POST /api/v1/simulations (request body = full reproduction spec)",
    )
    return SimulationStudyRead(
        report=report, conditions=results, comparisons=comparisons, scatter=scatter
    )
