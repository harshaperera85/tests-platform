"""LOFT session generation (BP-MODES-1 §4) — ``POST /loft/sessions``.

Generates unique conforming forms per session from a LOFT-bound blueprint, with
the §4.2 running exposure-rate cap applied across the batch and a §4.4
conformance record per session. This is both the LOFT preview surface and the
§7 verification harness shape; per-administration ledger recording arrives with
the Sessions module.
"""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.assembly.loft import LoftAssemblyError, assemble_loft_session
from app.core.db import get_db
from app.models.blueprint import BlueprintRow
from app.psychometrics import pools
from app.schemas.blueprint import Blueprint
from app.schemas.loft import LoftSessionRead, LoftSessionsRead, LoftSessionsRequest

router = APIRouter(prefix="/loft", tags=["loft"])


@router.post("/sessions", response_model=LoftSessionsRead)
def generate_loft_sessions(
    payload: LoftSessionsRequest, db: Session = Depends(get_db)
) -> LoftSessionsRead:
    bp_row = db.get(BlueprintRow, payload.blueprint_id)
    if bp_row is None:
        raise HTTPException(status_code=404, detail="blueprint not found")
    if not pools.is_known(payload.pool_id):
        raise HTTPException(
            status_code=404, detail=f"unknown pool_id {payload.pool_id!r}"
        )
    if pools.is_field_pool(payload.pool_id):
        raise HTTPException(
            status_code=422,
            detail=(
                "LOFT requires calibrated items (the §4.1 band and scoring need "
                "parameters) — field-study pools are content-only"
            ),
        )
    blueprint = Blueprint.model_validate(bp_row.spec)
    pool = pools.load_pool_by_id(payload.pool_id)

    usage: Counter[str] = Counter()
    sessions: list[LoftSessionRead] = []
    warnings: list[str] = []
    distinct: set[tuple[str, ...]] = set()
    for i in range(payload.n_sessions):
        seed = payload.seed * 1_000_003 + i
        try:
            form = assemble_loft_session(
                blueprint,
                pool,
                engine=payload.engine,
                seed=seed,
                usage_counts=dict(usage),
                n_prior_sessions=i,
            )
        except LoftAssemblyError as exc:
            # §4.3: a solver/search failure MUST fail the session start — never
            # administer a non-conforming form. Surface which session failed.
            raise HTTPException(
                status_code=422, detail=f"session {i + 1}: {exc}"
            ) from exc
        for w in form.warnings:
            if w not in warnings:
                warnings.append(w)
        record = dict(form.record)
        record["blueprint_id"] = payload.blueprint_id
        sessions.append(
            LoftSessionRead(
                session_index=i,
                seed=seed,
                item_ids=form.item_ids,
                tif_actual=form.tif_actual,
                record=record,
            )
        )
        usage.update(form.item_ids)
        distinct.add(tuple(sorted(form.item_ids)))

    max_rate = (
        max(usage.values()) / payload.n_sessions if usage else 0.0
    )
    return LoftSessionsRead(
        blueprint_id=payload.blueprint_id,
        pool_id=payload.pool_id,
        engine=payload.engine,
        n_sessions=payload.n_sessions,
        sessions=sessions,
        exposure=dict(usage),
        max_empirical_rate=max_rate,
        n_distinct_forms=len(distinct),
        warnings=warnings,
    )
