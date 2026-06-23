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


def test_phase1_paths_present(client: TestClient) -> None:
    """The Phase 1 resource paths Orval generates the client from (plan §9)."""
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/tests" in paths
    assert "/api/v1/tests/{test_id}" in paths
    assert "/api/v1/tests/{test_id}/assemble" in paths
    assert "/api/v1/tests/{test_id}/forms" in paths
    assert "/api/v1/blueprints" in paths
    assert "/api/v1/blueprints/{blueprint_id}" in paths
    assert "/api/v1/assembly-jobs" in paths
    assert "/api/v1/assembly-jobs/{job_id}" in paths
    assert "/api/v1/forms/{form_id}" in paths
    assert "/api/v1/preview/start" in paths
    assert "/api/v1/preview/respond" in paths
    assert "/api/v1/preview/score" in paths
    assert "/api/v1/pool/items" in paths
    assert "/api/v1/pool/catalog" in paths
    assert "/api/v1/scenarios" in paths
    assert "/api/v1/forms/{form_id}/tif-curve" in paths
    assert "/api/v1/forms/{form_id}/simulate" in paths


def test_operation_ids_are_clean_for_orval(client: TestClient) -> None:
    """operationIds = route function names, so Orval emits clean hook names."""
    schema = client.get("/openapi.json").json()
    op_ids = {
        op["operationId"]
        for path in schema["paths"].values()
        for op in path.values()
    }
    expected = {"create_blueprint", "create_assembly_job", "get_form", "start_preview"}
    assert expected <= op_ids


def test_blueprint_schema_exposed(client: TestClient) -> None:
    """The Blueprint schema must be named in components for Zod generation."""
    schema = client.get("/openapi.json").json()
    assert "Blueprint" in schema["components"]["schemas"]
