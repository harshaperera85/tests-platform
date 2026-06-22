"""The OpenAPI schema — source of the generated frontend client — is well-formed.

Guards the contract-first pipeline (CLAUDE.md golden rule 5): if this schema
breaks, Orval/Zod generation breaks.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_openapi_served(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["openapi"].startswith("3.")
    assert "/api/v1/health" in schema["paths"]
