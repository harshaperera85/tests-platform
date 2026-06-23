"""Observability: readiness probe shape + request-id propagation."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_readiness_reports_dependency_checks(client: TestClient) -> None:
    resp = client.get("/api/v1/health/ready")
    # 200 when deps are up, 503 when not — both are valid; assert the contract shape.
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ready", "degraded")
    assert "postgres" in body["checks"]
    assert "redis" in body["checks"]


def test_request_id_echoed(client: TestClient) -> None:
    # generated when absent
    r = client.get("/api/v1/health")
    assert r.headers.get("x-request-id")
    # echoed when provided
    r2 = client.get("/api/v1/health", headers={"x-request-id": "abc123"})
    assert r2.headers["x-request-id"] == "abc123"
