"""LOFT session-generation API schemas (BP-MODES-1 §4)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LoftSessionsRequest(BaseModel):
    """Generate ``n_sessions`` unique conforming forms for a LOFT-bound blueprint.

    Sessions are generated sequentially with the §4.2 running exposure-rate cap
    applied across the batch (session *i* is masked by the usage of sessions
    1..i−1) — the same shape as the §7 verification protocol. Live
    per-administration ledger recording arrives with the Sessions module.
    """

    blueprint_id: str
    pool_id: str
    n_sessions: int = Field(default=1, ge=1, le=2000)
    seed: int = 0
    engine: Literal["random_constrained", "cp_sat", "pregenerated"] = (
        "random_constrained"
    )
    #: engine (c) only: the test whose PUBLISHED forms constitute the
    #: pre-generated pool (batch-assembled, human-reviewed — §4.3(c)).
    test_id: str | None = None
    #: G5: persist the §4.4 conformance records (append-only,
    #: ``loft_session_record``). Default off for previews; the Sessions module
    #: will persist unconditionally per administration.
    persist_records: bool = False


class LoftSessionRead(BaseModel):
    session_index: int
    seed: int
    item_ids: list[str]
    tif_actual: list[float]
    #: the §4.4 conformance record (blueprint_conformant is true by construction)
    record: dict[str, Any]


class LoftSessionsRead(BaseModel):
    blueprint_id: str
    pool_id: str
    engine: str
    n_sessions: int
    sessions: list[LoftSessionRead]
    #: cumulative per-item usage across the generated batch
    exposure: dict[str, int]
    #: empirical max usage rate across items (uses / n_sessions)
    max_empirical_rate: float
    #: distinct forms drawn (diversity evidence)
    n_distinct_forms: int
    #: engine (c) only: size of the published pre-generated pool drawn from
    n_pool_forms: int | None = None
    #: G5: number of §4.4 records persisted by this call (0 unless requested)
    n_records_persisted: int = 0
    warnings: list[str]


class LoftRecordRead(BaseModel):
    """One persisted §4.4 conformance record (G5)."""

    id: str
    blueprint_id: str
    pool_id: str
    engine: str
    seed: int
    session_index: int
    item_ids: list[str]
    record: dict[str, Any]
    created_at: str
