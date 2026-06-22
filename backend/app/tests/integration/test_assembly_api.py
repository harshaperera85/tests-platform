"""Integration: the blueprint -> assembly-job -> form-preview API flow."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _blueprint_payload() -> dict:
    return {
        "name": "api-demo",
        "length": 12,
        "statistical_target": {
            "theta_points": [-1.0, 0.0, 1.0],
            "target_info": [5.0, 7.0, 5.0],
            "method": "minimax",
        },
        "content_constraints": [
            {"tag_type": "KC", "tag_value": "algebra", "minimum": 3, "maximum": 6}
        ],
    }


def test_blueprint_crud(client: TestClient) -> None:
    resp = client.post("/api/v1/blueprints", json=_blueprint_payload())
    assert resp.status_code == 201
    bid = resp.json()["id"]
    got = client.get(f"/api/v1/blueprints/{bid}")
    assert got.status_code == 200
    assert got.json()["blueprint"]["length"] == 12
    assert client.get("/api/v1/blueprints/missing").status_code == 404


def test_assemble_and_preview_form(client: TestClient) -> None:
    bid = client.post("/api/v1/blueprints", json=_blueprint_payload()).json()["id"]

    job = client.post(
        "/api/v1/assembly-jobs",
        json={"blueprint_id": bid, "strategy": "mip", "time_limit_s": 5},
    )
    assert job.status_code == 201
    body = job.json()
    assert body["status"] in ("optimal", "feasible")
    assert body["method"] == "minimax"
    assert len(body["form_ids"]) == 1

    # job is retrievable
    assert client.get(f"/api/v1/assembly-jobs/{body['id']}").status_code == 200

    form = client.get(f"/api/v1/forms/{body['form_ids'][0]}")
    assert form.status_code == 200
    fbody = form.json()
    assert len(fbody["item_ids"]) == 12
    # actual-vs-target points present and close
    assert len(fbody["tif"]) == 3
    for point in fbody["tif"]:
        assert point["gap"] == point["actual"] - point["target"]
        assert abs(point["gap"]) < 0.5


def test_assemble_missing_blueprint_404(client: TestClient) -> None:
    resp = client.post("/api/v1/assembly-jobs", json={"blueprint_id": "nope"})
    assert resp.status_code == 404


def test_form_not_found_404(client: TestClient) -> None:
    assert client.get("/api/v1/forms/nope").status_code == 404
