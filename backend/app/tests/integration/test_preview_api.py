"""Integration: the thin /preview dry-run drives LinearStrategy end-to-end.

The endpoint is stateless — the client carries ``state`` back each call — and all
sequencing/scoring lives in the strategy. These tests exercise the full walk:
start -> respond* -> score, plus the form_id path and error cases.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _blueprint_payload() -> dict:
    return {
        "name": "preview-demo",
        "length": 10,
        "statistical_target": {
            "theta_points": [-1.0, 0.0, 1.0],
            "target_info": [4.0, 6.0, 4.0],
            "method": "minimax",
        },
        "content_constraints": [
            {"tag_type": "KC", "tag_value": "algebra", "minimum": 2}
        ],
    }


def _walk(client: TestClient, start_body: dict) -> dict:
    start = client.post("/api/v1/preview/start", json=start_body)
    assert start.status_code == 200, start.text
    step = start.json()
    assert step["next_action"]["kind"] == "present"
    assert step["next_action"]["navigation"]["fixed_length"] is True

    steps = 0
    while step["next_action"]["kind"] == "present":
        item_id = step["next_action"]["payload"]["item_id"]
        resp = client.post(
            "/api/v1/preview/respond",
            json={"state": step["state"], "item_id": item_id, "correct": 1},
        )
        assert resp.status_code == 200, resp.text
        step = resp.json()
        steps += 1

    assert step["termination"]["complete"] is True
    assert step["termination"]["reason"] == "end_of_form"

    score = client.post("/api/v1/preview/score", json={"state": step["state"]})
    assert score.status_code == 200, score.text
    return {"steps": steps, "score": score.json()}


def test_preview_walkthrough_from_blueprint(client: TestClient) -> None:
    bid = client.post("/api/v1/blueprints", json=_blueprint_payload()).json()["id"]
    out = _walk(client, {"blueprint_id": bid})
    assert out["steps"] == 10
    score = out["score"]
    assert score["scale"] == "canonical"
    assert score["theta"] is not None
    assert score["standard_error"] is not None
    # all-correct should push theta above the prior mean
    assert score["theta"] > 0
    assert score["detail"]["n_answered"] == 10


def test_preview_walkthrough_from_form(client: TestClient) -> None:
    bid = client.post("/api/v1/blueprints", json=_blueprint_payload()).json()["id"]
    job = client.post(
        "/api/v1/assembly-jobs",
        json={"blueprint_id": bid, "strategy": "mip", "time_limit_s": 5},
    ).json()
    form_id = job["form_ids"][0]
    out = _walk(client, {"form_id": form_id})
    assert out["steps"] == 10


def test_preview_requires_a_source(client: TestClient) -> None:
    assert client.post("/api/v1/preview/start", json={}).status_code == 422


def test_preview_unknown_ids_404(client: TestClient) -> None:
    assert (
        client.post("/api/v1/preview/start", json={"blueprint_id": "nope"}).status_code
        == 404
    )
    assert (
        client.post("/api/v1/preview/start", json={"form_id": "nope"}).status_code
        == 404
    )
