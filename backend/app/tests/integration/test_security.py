"""Security posture: CORS is default-closed and opt-in via settings."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_no_cors_header_by_default() -> None:
    app = create_app()  # cors_origins == "" (default)
    client = TestClient(app)
    r = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_cors_allows_configured_origin(monkeypatch) -> None:
    monkeypatch.setattr(settings, "cors_origins", "http://app.example")
    app = create_app()
    client = TestClient(app)
    r = client.get("/health", headers={"Origin": "http://app.example"})
    assert r.headers.get("access-control-allow-origin") == "http://app.example"
