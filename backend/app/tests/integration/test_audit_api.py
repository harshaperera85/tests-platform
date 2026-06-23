"""Audit log: lifecycle actions are recorded and queryable."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _bp() -> dict:
    return {
        "name": "audit-bp",
        "length": 12,
        "statistical_target": {"theta_points": [-1, 0, 1], "target_info": [5, 7, 5]},
        "content_constraints": [
            {"tag_type": "KC", "tag_value": "algebra", "minimum": 3}
        ],
    }


def test_lifecycle_actions_are_audited(client: TestClient) -> None:
    tid = client.post(
        "/api/v1/tests", json={"name": "audited", "pool_id": "small_2pl"}
    ).json()["id"]
    client.patch(f"/api/v1/tests/{tid}", json={"blueprint": _bp()})
    client.post(f"/api/v1/tests/{tid}/assemble", json={"time_limit_s": 5})
    client.post(f"/api/v1/tests/{tid}/lock")

    events = client.get(f"/api/v1/audit?entity_id={tid}").json()
    actions = {e["action"] for e in events}
    assert {"test.create", "test.assemble", "test.lock"} <= actions
    # newest first, append-only shape
    assert events[0]["created_at"] >= events[-1]["created_at"]
    create = next(e for e in events if e["action"] == "test.create")
    assert create["entity_type"] == "test" and create["entity_id"] == tid


def test_audit_global_list_and_request_id(client: TestClient) -> None:
    client.post("/api/v1/tests", json={"name": "g", "pool_id": "small_2pl"})
    events = client.get("/api/v1/audit?limit=10").json()
    assert any(e["action"] == "test.create" for e in events)
    # request_id captured from the middleware context
    assert all("request_id" in e for e in events)
