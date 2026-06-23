"""Integration: simulated-bank exposure, dense TIF curve, simulated examinee.

These additive read-only endpoints let the UI demonstrate the linear workflow with
genuine simulated data and no real item-factory export.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _blueprint_payload() -> dict:
    return {
        "name": "sim-demo",
        "length": 12,
        "statistical_target": {
            "theta_points": [-1.0, 0.0, 1.0],
            "target_info": [5.0, 7.0, 5.0],
            "method": "minimax",
        },
        "content_constraints": [
            {"tag_type": "KC", "tag_value": "algebra", "minimum": 3}
        ],
    }


def _assemble(client: TestClient) -> str:
    bid = client.post("/api/v1/blueprints", json=_blueprint_payload()).json()["id"]
    job = client.post(
        "/api/v1/assembly-jobs",
        json={"blueprint_id": bid, "strategy": "mip", "time_limit_s": 5},
    ).json()
    return job["form_ids"][0]


def test_pool_items_exposes_simulated_bank(client: TestClient) -> None:
    resp = client.get("/api/v1/pool/items")
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["simulated"] is True
    assert doc["provenance"]
    assert doc["n_items"] == len(doc["items"]) == 48
    # tag availability summary the UI uses for feasibility hints
    assert doc["tag_summary"]["KC"]["algebra"] == 12
    # synthetic display content present, params intact
    first = doc["items"][0]
    assert first["stem"] and first["options"]
    assert first["a"] > 0 and "KC" in first["tags"]


def test_tif_curve_is_dense_and_grids_theta(client: TestClient) -> None:
    form_id = _assemble(client)
    url = f"/api/v1/forms/{form_id}/tif-curve?theta_min=-3&theta_max=3&n=61"
    resp = client.get(url)
    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "minimax"
    assert body["theta_points"] == [-1.0, 0.0, 1.0]
    assert len(body["curve"]) == 61
    assert body["curve"][0]["theta"] == -3.0 and body["curve"][-1]["theta"] == 3.0
    # information is non-negative and peaks somewhere in the middle of the range
    infos = [p["actual"] for p in body["curve"]]
    assert all(v >= 0 for v in infos)
    assert max(infos) > 0


def test_simulate_high_theta_examinee_scores_high(client: TestClient) -> None:
    form_id = _assemble(client)
    resp = client.get(f"/api/v1/forms/{form_id}/simulate?theta=2.0&seed=1")
    assert resp.status_code == 200
    sim = resp.json()
    assert sim["true_theta"] == 2.0
    assert sim["n_items"] == 12
    assert len(sim["trace"]) == 12
    # final estimate should land in the upper range for a true theta of 2.0
    assert sim["final_theta"] > 0.5
    # trace carries running estimates and per-item P(correct)
    assert all(0.0 <= s["prob_correct"] <= 1.0 for s in sim["trace"])
    assert sim["trace"][-1]["theta"] == sim["final_theta"]


def test_simulate_is_deterministic_by_seed(client: TestClient) -> None:
    form_id = _assemble(client)
    a = client.get(f"/api/v1/forms/{form_id}/simulate?theta=0&seed=7").json()
    b = client.get(f"/api/v1/forms/{form_id}/simulate?theta=0&seed=7").json()
    assert [s["response"] for s in a["trace"]] == [s["response"] for s in b["trace"]]


def test_simulate_unknown_form_404(client: TestClient) -> None:
    assert client.get("/api/v1/forms/nope/simulate").status_code == 404
    assert client.get("/api/v1/forms/nope/tif-curve").status_code == 404
