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
    engine: Literal["random_constrained", "cp_sat"] = "random_constrained"


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
    warnings: list[str]
