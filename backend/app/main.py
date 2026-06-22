"""FastAPI application entrypoint.

Mounts the versioned ``/api/v1`` router and exposes a root liveness check. The
OpenAPI schema produced here is the contract from which the frontend client is
generated (Orval + Zod) — never hand-write that client (CLAUDE.md golden rule 5).
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tests Platform API",
        version=__version__,
        description="Assembly + administration engine for a large testing program.",
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"], summary="Root liveness check")
    def root_health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name, "version": __version__}

    return app


app = create_app()
