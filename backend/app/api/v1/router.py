"""Aggregates all v1 routers under one ``APIRouter``.

New resource routers (tests, section-templates, cat-config, preview — plan §9) are
included here as they land.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import assembly_jobs, blueprints, forms, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(blueprints.router)
api_router.include_router(assembly_jobs.router)
api_router.include_router(forms.router)
