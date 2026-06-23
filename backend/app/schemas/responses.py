"""API response schemas (the OpenAPI contract; plan §9).

These typed responses are what Orval + Zod generate the frontend client from — never
hand-write that client (CLAUDE.md golden rule 5).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.blueprint import Blueprint


class BlueprintRead(BaseModel):
    id: str
    name: str
    length: int
    num_forms: int
    created_at: datetime
    blueprint: Blueprint


class AssemblyJobCreate(BaseModel):
    blueprint_id: str
    pool_id: str = "small_2pl"
    strategy: str = "mip"
    seed: int = 0
    time_limit_s: float = 10.0


class AssemblyJobRead(BaseModel):
    id: str
    blueprint_id: str
    pool_id: str
    strategy: str
    status: str
    method: str | None = None
    objective_value: float | None = None
    theta_points: list[float] = []
    target_info: list[float] = []
    warnings: list[str] = []
    form_ids: list[str] = []
    created_at: datetime


class ScenarioRead(BaseModel):
    """A named demo scenario: a pool + blueprint preset exercising one capability."""

    scenario_id: str
    title: str
    description: str
    pool_id: str
    blueprint: Blueprint
    note: str  # what to look for when assembling/previewing it


class TIFPoint(BaseModel):
    theta: float
    target: float
    actual: float
    gap: float  # actual - target


class FormRead(BaseModel):
    id: str
    blueprint_id: str
    assembly_job_id: str
    form_index: int
    status: str
    item_ids: list[str]
    created_at: datetime
    #: actual-vs-target TIF, point by point — drives the preview plot.
    tif: list[TIFPoint]


class TIFCurvePoint(BaseModel):
    theta: float
    actual: float


class TIFCurve(BaseModel):
    """Dense actual TIF over a theta grid (server-computed via psychometrics) plus
    the discrete blueprint target points — for a smooth actual-vs-target plot."""

    theta_points: list[float]  # blueprint target thetas
    target_info: list[float]
    tolerance: float | None = None
    method: str
    curve: list[TIFCurvePoint]


class SimulationStepRead(BaseModel):
    position: int
    item_id: str
    prob_correct: float
    response: int
    theta: float | None = None
    standard_error: float | None = None


class SimulationRead(BaseModel):
    """A genuine simulated examinee session over a form (real engine + 2PL model)."""

    form_id: str
    true_theta: float
    seed: int
    n_items: int
    final_theta: float | None = None
    final_standard_error: float | None = None
    trace: list[SimulationStepRead]
