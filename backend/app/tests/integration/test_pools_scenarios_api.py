"""Integration: pool catalog + selection and demo scenarios.

The mixed demo bank makes previously-uncoverable use cases demonstrable; selection
threads a chosen pool through assemble → form → preview/tif-curve/simulate.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_pool_catalog_lists_both_banks(client: TestClient) -> None:
    body = client.get("/api/v1/pool/catalog").json()
    assert body["default_pool_id"] == "small_2pl"
    by_id = {p["pool_id"]: p for p in body["pools"]}
    assert set(by_id) >= {"small_2pl", "demo_mixed"}
    demo = by_id["demo_mixed"]
    assert demo["n_items"] == 252
    assert demo["n_3pl"] > 0
    assert set(demo["domains"]) == {"math", "science", "ela"}


def test_pool_items_selects_bank(client: TestClient) -> None:
    small = client.get("/api/v1/pool/items").json()  # default
    assert small["pool_id"] == "small_2pl" and small["n_items"] == 48
    demo = client.get("/api/v1/pool/items?pool_id=demo_mixed").json()
    assert demo["pool_id"] == "demo_mixed" and demo["n_items"] == 252
    assert "science" in demo["tag_summary"]["domain"]
    assert client.get("/api/v1/pool/items?pool_id=nope").status_code == 404


def test_scenarios_listed_and_assemblable(client: TestClient) -> None:
    scenarios = client.get("/api/v1/scenarios").json()
    ids = {s["scenario_id"] for s in scenarios}
    assert {"multi_domain", "parallel_exposure", "mastery_cut", "guessing_3pl"} <= ids

    # the multi-domain scenario assembles on its pool and satisfies its constraints
    multi = next(s for s in scenarios if s["scenario_id"] == "multi_domain")
    bid = client.post("/api/v1/blueprints", json=multi["blueprint"]).json()["id"]
    job = client.post(
        "/api/v1/assembly-jobs",
        json={"blueprint_id": bid, "pool_id": multi["pool_id"], "time_limit_s": 8},
    ).json()
    assert job["status"] in ("optimal", "feasible")
    assert job["pool_id"] == "demo_mixed"
    assert len(job["form_ids"]) == 1


def test_demo_pool_threads_through_form_endpoints(client: TestClient) -> None:
    # assemble on the demo pool, then form-scoped endpoints resolve that pool.
    bp = {
        "name": "demo-thread",
        "length": 20,
        "statistical_target": {
            "theta_points": [-1, 0, 1],
            "target_info": [8, 10, 8],
            "method": "minimax",
        },
        "content_constraints": [
            {"tag_type": "domain", "tag_value": "science", "minimum": 5}
        ],
    }
    bid = client.post("/api/v1/blueprints", json=bp).json()["id"]
    job = client.post(
        "/api/v1/assembly-jobs",
        json={"blueprint_id": bid, "pool_id": "demo_mixed", "time_limit_s": 8},
    ).json()
    assert job["status"] in ("optimal", "feasible")
    form_id = job["form_ids"][0]

    # tif-curve + simulate work against the demo pool (item_ids resolve there)
    curve = client.get(f"/api/v1/forms/{form_id}/tif-curve?n=21")
    assert curve.status_code == 200 and len(curve.json()["curve"]) == 21
    sim = client.get(f"/api/v1/forms/{form_id}/simulate?theta=1.5&seed=2")
    assert sim.status_code == 200 and sim.json()["final_theta"] is not None

    # preview from the form resolves the demo pool too
    start = client.post("/api/v1/preview/start", json={"form_id": form_id})
    assert start.status_code == 200
    assert start.json()["next_action"]["kind"] == "present"


def test_parallel_exposure_scenario_zero_overlap(client: TestClient) -> None:
    scenarios = client.get("/api/v1/scenarios").json()
    s = next(s for s in scenarios if s["scenario_id"] == "parallel_exposure")
    bid = client.post("/api/v1/blueprints", json=s["blueprint"]).json()["id"]
    job = client.post(
        "/api/v1/assembly-jobs",
        json={"blueprint_id": bid, "pool_id": s["pool_id"], "time_limit_s": 20},
    ).json()
    assert job["status"] in ("optimal", "feasible")
    assert len(job["form_ids"]) == 3
    forms = [
        client.get(f"/api/v1/forms/{fid}").json()["item_ids"]
        for fid in job["form_ids"]
    ]
    seen: set[str] = set()
    for ids in forms:
        assert seen.isdisjoint(ids)  # exposure max_use=1 -> no reuse
        seen.update(ids)
