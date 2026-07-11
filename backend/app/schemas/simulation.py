"""Measurement-simulation harness schemas (G1, `docs/loft_literature_review.md`).

One request = one *study*: a shared simulee population run through 1–4 named
design conditions. Per the shared simulation-lane conventions
(`docs/ignite-contracts/ignite-2026-07-10-fe51314/simulation-lane-conventions.md`):
responses carry a §4-format report block, and seeding follows C5 (per-simulee
RNGs derived from ``(seed, simulee_index)``, item-level response draws derived
from ``(seed, simulee_index, item_id)`` — order-independent, and identical items
get identical responses across conditions, so cross-condition comparisons are
paired at the item level).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class LinearDesign(BaseModel):
    """A fixed-form condition: one form assembled once (or given), walked by all
    simulees. This is the Embretson-style *baseline* design."""

    kind: Literal["linear"] = "linear"
    blueprint_id: str | None = None
    #: pre-assembled alternative to blueprint_id (skips assembly)
    form_id: str | None = None
    assembly_strategy: Literal["mip", "random_constrained"] = "mip"

    @model_validator(mode="after")
    def _one_source(self) -> LinearDesign:
        if (self.blueprint_id is None) == (self.form_id is None):
            raise ValueError("linear design needs exactly one of blueprint_id/form_id")
        return self


class LoftDesign(BaseModel):
    """A LOFT condition: one conforming form assembled per simulee via the real
    §4 engine; the running exposure-rate cap accumulates across the condition.

    Engine (c) ``pregenerated`` batch-assembles ``n_pool_forms`` forms ONCE via
    the real production ``assemble()`` (mip), then each simulee *draws* from
    that pool (least-drawn rotation, seeded tie-break) — the Luecht & Sireci
    batch-in-advance variant, so a study can compare pool sizes directly."""

    kind: Literal["loft"] = "loft"
    blueprint_id: str
    engine: Literal["random_constrained", "cp_sat", "pregenerated"] = (
        "random_constrained"
    )
    #: engine (c) only: size of the batch-assembled pool (K)
    n_pool_forms: int = Field(default=20, ge=2, le=50)


Design = Annotated[LinearDesign | LoftDesign, Field(discriminator="kind")]


class Condition(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_ -]{0,39}$")
    design: Design


class Population(BaseModel):
    distribution: Literal["normal", "uniform"] = "normal"
    mean: float = 0.0
    sd: float = Field(default=1.0, gt=0.0)
    low: float = -3.0
    high: float = 3.0


class SimulationRequest(BaseModel):
    pool_id: str
    conditions: list[Condition] = Field(min_length=1, max_length=4)
    population: Population = Field(default_factory=Population)
    n_simulees: int = Field(default=500, ge=10, le=2000)
    replications: int = Field(default=1, ge=1, le=20)
    seed: int = 0

    @model_validator(mode="after")
    def _bounded_total(self) -> SimulationRequest:
        total = self.n_simulees * self.replications * len(self.conditions)
        if total > 20_000:
            raise ValueError(
                f"study size {total} simulee-sessions exceeds the synchronous cap "
                "(20,000); reduce n_simulees × replications × conditions"
            )
        names = [c.name for c in self.conditions]
        if len(set(names)) != len(names):
            raise ValueError("condition names must be unique")
        return self


# ------------------------------------------------------------------- results
class OverallStats(BaseModel):
    n: int
    mean_bias: float
    mean_mae: float
    rmse: float
    mean_see: float
    correlation: float
    reliability: float
    true_theta_sd: float
    est_theta_sd: float
    #: Embretson caution: SD(θ̂)/SD(θ) — EAP shrinkage makes low SEs deceptive
    shrinkage_ratio: float
    mean_length: float


class ConditionalBin(BaseModel):
    bin_center: float
    n: int
    cbias: float | None = None
    cmae: float | None = None
    csee: float | None = None
    crmse: float | None = None


class ExposureStats(BaseModel):
    n_items_used: int
    max_rate: float
    mean_rate: float
    #: LOFT only: distinct forms drawn / sessions
    n_distinct_forms: int | None = None
    #: LOFT only: mean/max pairwise overlap proportion over sampled session pairs
    mean_pairwise_overlap: float | None = None
    max_pairwise_overlap: float | None = None
    #: per-item exposure rates (item_id -> rate), capped to the busiest 200
    rates: dict[str, float]


class ConditionResult(BaseModel):
    name: str
    kind: str
    overall: OverallStats
    conditional: list[ConditionalBin]
    exposure: ExposureStats
    #: sessions whose assembly failed loudly (LOFT §4.3) — a pool-health metric
    n_infeasible_sessions: int
    assembly_seconds_mean: float | None = None
    assembly_seconds_p95: float | None = None
    warnings: list[str]


class PairedComparison(BaseModel):
    """Paired at the simulee level (shared true θ + item-level response seeds):
    Δ = |error|_a − |error|_b per simulee; negative mean favors condition a."""

    condition_a: str
    condition_b: str
    n_pairs: int
    mean_abs_error_delta: float
    rmse_a: float
    rmse_b: float
    #: paired z-test on the per-simulee |error| differences
    z: float | None = None
    p_value: float | None = None


class ReportLane(BaseModel):
    lane: str
    coverage: str


class ReportBlock(BaseModel):
    """§4 shared verification-report header (simulation-lane conventions)."""

    protocol: str
    date: str
    engine: str
    lanes: list[ReportLane]
    seeds: dict[str, int]
    n_per_condition: int
    inputs: dict[str, str]
    driver: str


class SimulationStudyRead(BaseModel):
    report: ReportBlock
    conditions: list[ConditionResult]
    comparisons: list[PairedComparison]
    #: (true, est) pairs from the FIRST condition, downsampled for scatter plots
    scatter: list[tuple[float, float]]
