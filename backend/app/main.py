"""FastAPI application entrypoint.

Mounts the versioned ``/api/v1`` router and exposes a root liveness check. The
OpenAPI schema produced here is the contract from which the frontend client is
generated (Orval + Zod) — never hand-write that client (CLAUDE.md golden rule 5).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import RequestIdMiddleware
from app.engine import strategies as _strategies  # noqa: F401  (registers strategies)


def _operation_id(route: APIRoute) -> str:
    """Use the route's function name as the OpenAPI operationId.

    OpenAPI-metadata only (no behavior change): it gives the generated frontend
    client clean hook names (e.g. ``useCreateBlueprint``) — contract-first,
    golden rule 5.
    """
    return route.name


def create_app() -> FastAPI:
    setup_logging(level="DEBUG" if settings.debug else "INFO")
    app = FastAPI(
        title="Tests Platform API",
        version=__version__,
        description="Assembly + administration engine for a large testing program.",
        generate_unique_id_function=_operation_id,
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"], summary="Root liveness check")
    def root_health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name, "version": __version__}

    return app


app = create_app()
