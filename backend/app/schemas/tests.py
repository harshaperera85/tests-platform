"""API schemas for the ``tests`` resource (plan §8/§9).

A test owns an editable blueprint draft (``blueprint``), a pool, an administration
model, and a status. These typed models are part of the OpenAPI contract the
frontend client is generated from (golden rule 5).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.blueprint import Blueprint


class TestCreate(BaseModel):
    name: str = "Untitled test"
    administration_model: str = "linear"
    pool_id: str = "demo_mixed"
    blueprint: Blueprint | None = None


class TestUpdate(BaseModel):
    """PATCH — only provided fields are applied."""

    name: str | None = None
    pool_id: str | None = None
    blueprint: Blueprint | None = None


class TestSummary(BaseModel):
    id: str
    name: str
    administration_model: str
    status: str
    pool_id: str
    version: int
    form_count: int
    has_blueprint: bool
    created_at: datetime
    updated_at: datetime


class TestRead(BaseModel):
    id: str
    name: str
    administration_model: str
    status: str
    pool_id: str
    version: int
    blueprint: Blueprint | None
    form_count: int
    created_at: datetime
    updated_at: datetime


class TestAssembleRequest(BaseModel):
    strategy: str = "mip"
    seed: int = 0
    time_limit_s: float = 12.0


class FormSummary(BaseModel):
    id: str
    assembly_job_id: str
    blueprint_id: str
    pool_id: str
    form_index: int
    status: str
    n_items: int
    created_at: datetime
