"""Aggregates all v1 routers under one ``APIRouter``.

New resource routers (tests, blueprints, assembly-jobs, forms, cat-config,
preview — plan §9) are included here as they land.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
