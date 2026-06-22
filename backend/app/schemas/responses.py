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
    strategy: str = "mip"
    seed: int = 0
    time_limit_s: float = 10.0


class AssemblyJobRead(BaseModel):
    id: str
    blueprint_id: str
    strategy: str
    status: str
    method: str | None = None
    objective_value: float | None = None
    theta_points: list[float] = []
    target_info: list[float] = []
    warnings: list[str] = []
    form_ids: list[str] = []
    created_at: datetime


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
