"""Application settings.

Single source of configuration, loaded from environment / ``.env`` via
pydantic-settings. Nothing here reaches out to a service at import time — wiring
(``core/db.py``, ``core/redis.py``) consumes these values lazily.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app ---
    app_name: str = "tests-platform"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # --- datastores ---
    database_url: str = "postgresql+psycopg://tests:tests@postgres:5432/tests"
    redis_url: str = "redis://redis:6379/0"

    # --- jobs ---
    # When true, assembly solves are enqueued to RQ (a worker executes them);
    # when false they run inline in-request. Default false so the API works
    # without a worker/Redis (tests); docker-compose sets it true.
    assembly_async: bool = False

    # --- capability services ---
    scoring_r_url: str = "http://scoring-r:8000"
    # CAT platform endpoints are pinned before Phase 2 (see plan §16). Adapter
    # default is unset locally.
    cat_platform_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (import-safe, test-overridable)."""
    return Settings()


settings = get_settings()
