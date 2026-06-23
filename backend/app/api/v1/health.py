"""Health endpoint under the versioned API.

Liveness only in Phase 0 — does not dial Postgres/Redis (readiness probes that do
arrive with the data model in Phase 1).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.core.config import settings
from app.core.db import get_engine
from app.core.redis import get_redis

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, str]  # dependency -> "ok" | "error: ..."


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
    )


@router.get(
    "/health/ready", response_model=ReadinessResponse, summary="Readiness check"
)
def readiness(response: Response) -> ReadinessResponse:
    """Verify dependencies (Postgres, Redis). 503 if any are unreachable."""
    checks: dict[str, str] = {}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report any connectivity failure
        checks["postgres"] = f"error: {exc}"
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"

    ready = all(v == "ok" for v in checks.values())
    if not ready:
        response.status_code = 503
    return ReadinessResponse(status="ready" if ready else "degraded", checks=checks)
