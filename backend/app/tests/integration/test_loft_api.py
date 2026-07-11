"""POST /loft/sessions — §4 end-to-end + a §7-style verification run.

The §7 protocol calls for N ≥ 1,000 simulated sessions; the CI-sized run here
uses N = 150 with the identical assertions (100% conformant by construction,
band held at every θ point in every session, empirical exposure ≤ rate + ε,
form diversity). The full-scale run belongs to the simulation harness.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _loft_blueprint_payload(rate: float | None = None) -> dict:
    payload: dict = {
        "name": "loft-api",
        "length": 12,
        "statistical_target": {
            "theta_points": [-1.0, 0.0, 1.0],
            "target_info": [4.5, 5.5, 4.5],
            "tolerance": 1.5,
        },
        "content_constraints": [
            {"tag_type": "KC", "tag_value": "algebra", "minimum": 2, "maximum": 5},
            {"tag_type": "KC", "tag_value": "geometry", "minimum": 2},
        ],
    }
    if rate is not None:
        payload["exposure_target"] = {"max_exposure_rate": rate}
    return payload


def _create_blueprint(client: TestClient, rate: float | None = None) -> str:
    resp = client.post("/api/v1/blueprints", json=_loft_blueprint_payload(rate))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_loft_sessions_verification_run(client: TestClient) -> None:
    """§7-style: every session conformant, band held, exposure capped, diverse."""
    rate = 0.6
    bid = _create_blueprint(client, rate=rate)
    n = 150
    resp = client.post(
        "/api/v1/loft/sessions",
        json={
            "blueprint_id": bid,
            "pool_id": "small_2pl",
            "n_sessions": n,
            "seed": 7,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["n_sessions"] == n and len(body["sessions"]) == n

    # 100% conformant by construction; band held at every theta in every session
    for s in body["sessions"]:
        r = s["record"]
        assert r["blueprint_conformant"] is True
        assert all(c["satisfied"] for c in r["constraints"])
        for actual, target in zip(r["tif_actual"], r["tif_target"], strict=True):
            assert abs(actual - target) <= r["tolerance"] + 1e-9

    # empirical exposure <= rate + eps (eps = one session's worth of slack:
    # the running cap uses the count BEFORE each session)
    assert body["max_empirical_rate"] <= rate + 1.0 / n + 1e-9

    # per-examinee uniqueness in the aggregate: many distinct forms
    assert body["n_distinct_forms"] >= n / 5


def test_loft_sessions_cp_sat_engine(client: TestClient) -> None:
    bid = _create_blueprint(client)
    resp = client.post(
        "/api/v1/loft/sessions",
        json={
            "blueprint_id": bid,
            "pool_id": "small_2pl",
            "n_sessions": 8,
            "seed": 3,
            "engine": "cp_sat",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["n_distinct_forms"] >= 3
    assert all(
        s["record"]["engine"] == "cp_sat" and s["record"]["blueprint_conformant"]
        for s in body["sessions"]
    )


def test_loft_sessions_validation_errors(client: TestClient) -> None:
    # target without tolerance -> per-session binding failure -> 422
    no_tol = _loft_blueprint_payload()
    del no_tol["statistical_target"]["tolerance"]
    bid = client.post("/api/v1/blueprints", json=no_tol).json()["id"]
    resp = client.post(
        "/api/v1/loft/sessions",
        json={"blueprint_id": bid, "pool_id": "small_2pl"},
    )
    assert resp.status_code == 422
    assert "tolerance" in resp.json()["detail"]

    # unknown blueprint / pool -> 404
    assert (
        client.post(
            "/api/v1/loft/sessions",
            json={"blueprint_id": "ghost", "pool_id": "small_2pl"},
        ).status_code
        == 404
    )
    bid2 = _create_blueprint(client)
    assert (
        client.post(
            "/api/v1/loft/sessions",
            json={"blueprint_id": bid2, "pool_id": "nope"},
        ).status_code
        == 404
    )


def test_loft_impossible_band_fails_the_session_start(client: TestClient) -> None:
    payload = _loft_blueprint_payload()
    payload["statistical_target"]["target_info"] = [40.0, 40.0, 40.0]
    payload["statistical_target"]["tolerance"] = 0.1
    bid = client.post("/api/v1/blueprints", json=payload).json()["id"]
    resp = client.post(
        "/api/v1/loft/sessions",
        json={"blueprint_id": bid, "pool_id": "small_2pl", "n_sessions": 2},
    )
    assert resp.status_code == 422
    assert "session 1" in resp.json()["detail"]  # failed loudly, nothing returned


# ---------------------------------------- §4.3(c) pre-generated pool (G2)
def _publish(client: TestClient, form_id: str) -> None:
    for action, kw in [
        ("submit_for_review", {"actor": "author@x"}),
        ("approve_content", {"actor": "sme@x", "actor_role": "content_reviewer"}),
        (
            "approve_psychometric",
            {"actor": "psy@x", "actor_role": "psychometrician"},
        ),
        ("publish", {"actor": "admin@x", "actor_role": "publisher"}),
    ]:
        r = client.post(
            f"/api/v1/forms/{form_id}/transition", json={"action": action, **kw}
        )
        assert r.status_code == 200, r.text


def _test_with_published_pool(
    client: TestClient, n_forms: int = 4, publish: int | None = None
) -> tuple[str, str, list[str]]:
    """Create a test, batch-assemble n_forms, publish the first `publish` of
    them; returns (test_id, blueprint_id of the assembly snapshot, form_ids)."""
    tid = client.post(
        "/api/v1/tests", json={"name": "loft-c", "pool_id": "small_2pl"}
    ).json()["id"]
    bp = _loft_blueprint_payload()
    bp["num_forms"] = n_forms
    bp["exposure_target"] = {"max_use_per_item": 2}  # batch diversity pressure
    r = client.patch(f"/api/v1/tests/{tid}", json={"blueprint": bp})
    assert r.status_code == 200, r.text
    job = client.post(
        f"/api/v1/tests/{tid}/assemble", json={"strategy": "mip", "time_limit_s": 20}
    ).json()
    assert len(job["form_ids"]) == n_forms, job
    for fid in job["form_ids"][: (publish if publish is not None else n_forms)]:
        _publish(client, fid)
    return tid, job["blueprint_id"], job["form_ids"]


def test_pregenerated_draws_only_published_reviewed_forms(
    client: TestClient,
) -> None:
    tid, bid, form_ids = _test_with_published_pool(client, n_forms=4, publish=3)
    resp = client.post(
        "/api/v1/loft/sessions",
        json={
            "blueprint_id": bid,
            "pool_id": "small_2pl",
            "engine": "pregenerated",
            "test_id": tid,
            "n_sessions": 9,
            "seed": 7,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["n_pool_forms"] == 3  # the unpublished 4th form is NOT drawable
    assert body["engine"] == "pregenerated"
    drawn = {s["record"]["form_id"] for s in body["sessions"]}
    assert drawn <= set(form_ids[:3]) and form_ids[3] not in drawn
    # rotation: 9 sessions over K=3 -> every published form drawn exactly 3×
    from collections import Counter

    per_form = Counter(s["record"]["form_id"] for s in body["sessions"])
    assert sorted(per_form.values()) == [3, 3, 3]
    assert body["n_distinct_forms"] == 3
    for s in body["sessions"]:
        assert s["record"]["blueprint_conformant"] is True
        assert s["record"]["engine"] == "pregenerated"


def test_pregenerated_validation_errors(client: TestClient) -> None:
    bid = _create_blueprint(client)
    # missing test_id
    r = client.post(
        "/api/v1/loft/sessions",
        json={
            "blueprint_id": bid,
            "pool_id": "small_2pl",
            "engine": "pregenerated",
        },
    )
    assert r.status_code == 422 and "test_id" in r.json()["detail"]
    # unknown test
    r = client.post(
        "/api/v1/loft/sessions",
        json={
            "blueprint_id": bid,
            "pool_id": "small_2pl",
            "engine": "pregenerated",
            "test_id": "ghost",
        },
    )
    assert r.status_code == 404
    # test with no published forms
    tid, bid2, _ = _test_with_published_pool(client, n_forms=2, publish=0)
    r = client.post(
        "/api/v1/loft/sessions",
        json={
            "blueprint_id": bid2,
            "pool_id": "small_2pl",
            "engine": "pregenerated",
            "test_id": tid,
        },
    )
    assert r.status_code == 422 and "no published forms" in r.json()["detail"]
