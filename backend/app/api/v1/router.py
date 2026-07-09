"""Aggregates all v1 routers under one ``APIRouter``.

New resource routers (tests, section-templates, cat-config, preview — plan §9) are
included here as they land.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    assembly_jobs,
    audit,
    blueprints,
    curricula,
    forms,
    health,
    item_bank,
    pool,
    preview,
    scenarios,
    tests,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(tests.router)
api_router.include_router(audit.router)
api_router.include_router(blueprints.router)
api_router.include_router(curricula.router)
api_router.include_router(item_bank.router)
api_router.include_router(assembly_jobs.router)
api_router.include_router(forms.router)
api_router.include_router(pool.router)
api_router.include_router(scenarios.router)
api_router.include_router(preview.router)
