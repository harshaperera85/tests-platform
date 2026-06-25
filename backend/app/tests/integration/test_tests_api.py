"""Integration: the ``tests`` resource (CRUD, list, draft, assemble, history, lock).

Server-backs the Phase 1.6 authoring IA (replacing the client-side registry).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _bp(length: int = 12) -> dict:
    return {
        "name": "t1",
        "length": length,
        "statistical_target": {
            "theta_points": [-1, 0, 1],
            "target_info": [5, 7, 5],
            "method": "minimax",
        },
        "content_constraints": [
            {"tag_type": "KC", "tag_value": "algebra", "minimum": 3}
        ],
    }


def test_create_list_get_test(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tests", json={"name": "My test", "pool_id": "demo_mixed"}
    )
    assert created.status_code == 201
    tid = created.json()["id"]
    assert created.json()["status"] == "draft"
    assert created.json()["administration_model"] == "linear"

    listing = client.get("/api/v1/tests").json()
    assert any(t["id"] == tid and t["name"] == "My test" for t in listing)

    got = client.get(f"/api/v1/tests/{tid}").json()
    assert got["pool_id"] == "demo_mixed"
    assert got["blueprint"] is None and got["form_count"] == 0
    assert client.get("/api/v1/tests/nope").status_code == 404


def test_patch_persists_draft(client: TestClient) -> None:
    tid = client.post("/api/v1/tests", json={"name": "draft"}).json()["id"]
    r = client.patch(
        f"/api/v1/tests/{tid}", json={"name": "renamed", "blueprint": _bp()}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "renamed"
    assert body["blueprint"]["length"] == 12
    assert body["version"] == 2  # bumped from 1
    # reload reflects the persisted draft (no client state)
    assert client.get(f"/api/v1/tests/{tid}").json()["blueprint"]["length"] == 12


def test_assemble_from_test_then_history(client: TestClient) -> None:
    tid = client.post(
        "/api/v1/tests", json={"name": "asm", "pool_id": "demo_mixed"}
    ).json()["id"]
    # cannot assemble without a blueprint draft
    assert client.post(f"/api/v1/tests/{tid}/assemble", json={}).status_code == 422

    client.patch(f"/api/v1/tests/{tid}", json={"blueprint": _bp()})
    job = client.post(f"/api/v1/tests/{tid}/assemble", json={"time_limit_s": 6})
    assert job.status_code == 201
    jb = job.json()
    assert jb["status"] in ("optimal", "feasible")
    assert jb["pool_id"] == "demo_mixed"
    form_id = jb["form_ids"][0]

    # form history for the test
    forms = client.get(f"/api/v1/tests/{tid}/forms").json()
    assert len(forms) == 1 and forms[0]["id"] == form_id and forms[0]["n_items"] == 12

    # the assembled form resolves on its own endpoints (test_id linkage intact)
    assert client.get(f"/api/v1/forms/{form_id}").status_code == 200
    assert client.get(f"/api/v1/tests/{tid}").json()["form_count"] == 1


def test_status_and_freeze_derived_from_lifecycle(client: TestClient) -> None:
    """No manual lock: test status + editability are derived from form lifecycle."""
    # the retired endpoints are gone
    tid = client.post("/api/v1/tests", json={"name": "lk"}).json()["id"]
    assert client.post(f"/api/v1/tests/{tid}/lock").status_code == 404
    assert client.post(f"/api/v1/tests/{tid}/unlock").status_code == 404

    assert client.get(f"/api/v1/tests/{tid}").json()["status"] == "draft"
    client.patch(f"/api/v1/tests/{tid}", json={"blueprint": _bp()})
    job = client.post(f"/api/v1/tests/{tid}/assemble", json={"time_limit_s": 6}).json()
    fid = job["form_ids"][0]
    # all forms draft → test status draft, still editable
    assert client.get(f"/api/v1/tests/{tid}").json()["status"] == "draft"
    assert client.patch(f"/api/v1/tests/{tid}", json={"name": "ok"}).status_code == 200

    # move the form into review → test status derives to in_review, and freezes
    client.post(f"/api/v1/forms/{fid}/transition", json={"action": "submit_for_review"})
    assert client.get(f"/api/v1/tests/{tid}").json()["status"] == "in_review"
    assert client.patch(
        f"/api/v1/tests/{tid}", json={"blueprint": _bp()}
    ).status_code == 409
    assert client.post(f"/api/v1/tests/{tid}/assemble", json={}).status_code == 409

    # return to draft unfreezes + reverts the derived status
    client.post(
        f"/api/v1/forms/{fid}/transition",
        json={"action": "return_to_draft", "actor": "sme", "comment": "rework"},
    )
    assert client.get(f"/api/v1/tests/{tid}").json()["status"] == "draft"
    assert client.patch(f"/api/v1/tests/{tid}", json={"name": "x"}).status_code == 200


def test_duplicate_and_delete(client: TestClient) -> None:
    tid = client.post("/api/v1/tests", json={"name": "orig"}).json()["id"]
    client.patch(f"/api/v1/tests/{tid}", json={"blueprint": _bp()})
    dup = client.post(f"/api/v1/tests/{tid}/duplicate")
    assert dup.status_code == 201
    assert dup.json()["name"] == "orig (copy)"
    assert dup.json()["blueprint"]["length"] == 12
    assert dup.json()["id"] != tid

    assert client.delete(f"/api/v1/tests/{tid}").status_code == 204
    assert client.get(f"/api/v1/tests/{tid}").status_code == 404
