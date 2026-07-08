"""POST /blueprints/generate + GET /curricula — §6 generator endpoints
(rev. 2026-07-09: test types, dimension weights, imputation reporting)."""

from __future__ import annotations

from fastapi.testclient import TestClient

PRE_ALGEBRA = "36e3fbed-61f1-4454-a41c-93e665bb1715"  # shipped catalog course

# An inline manifest whose KC ids match the demo pool's KC tag values.
MANIFEST = {
    "course_id": "demo-course",
    "course_name": "Demo Course",
    "units": [
        {
            "unit_id": "u1",
            "order": 1,
            "name": "Unit One",
            "kcs": [
                {"kc_id": "algebra", "order": 1, "n_complicators": 3},
                {"kc_id": "number", "order": 2, "n_complicators": 2},
            ],
        }
    ],
}


def test_curricula_catalog(client: TestClient) -> None:
    resp = client.get("/api/v1/curricula")
    assert resp.status_code == 200
    entries = {e["course_id"]: e for e in resp.json()}
    assert PRE_ALGEBRA in entries
    entry = entries[PRE_ALGEBRA]
    assert entry["course_name"] == "Pre-Algebra New"
    assert entry["n_units"] == 11 and entry["n_kcs"] == 60

    one = client.get(f"/api/v1/curricula/{PRE_ALGEBRA}")
    assert one.status_code == 200
    assert len(one.json()["units"]) == 11
    assert client.get("/api/v1/curricula/nope").status_code == 404


def test_generate_cumulative_final_from_catalog(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={"course_id": PRE_ALGEBRA, "test_type": "cumulative_final", "length": 60},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # §6.1 on the shipped catalog: 16 authored kc_configs, the rest imputed at
    # the median (5) — 183 of 199 complicators
    assert [s["count"] for s in body["shares"]] == [6, 5, 10, 3, 6, 6, 6, 4, 6, 5, 3]
    assert abs(body["imputed_fraction"] - 183 / 199) < 1e-9
    assert any("imputed" in w for w in body["warnings"])
    bp = body["blueprint"]
    assert bp["schema_version"] == 2
    assert bp["statistical_target"] is None  # CAT default: content-only
    # CAT binding -> proportion cells (scale-free under emergent length)
    assert all(c["mode"] == "proportion" for c in bp["content_constraints"])
    assert body["feasibility_checked"] is False  # no pool_id supplied
    # not auto-saved: the blueprint round-trips through explicit create
    created = client.post("/api/v1/blueprints", json=bp)
    assert created.status_code == 201, created.text


def test_generate_mid_and_end_of_course_scopes(client: TestClient) -> None:
    mid = client.post(
        "/api/v1/blueprints/generate",
        json={"course_id": PRE_ALGEBRA, "test_type": "mid_course", "length": 30},
    ).json()
    eoc = client.post(
        "/api/v1/blueprints/generate",
        json={"course_id": PRE_ALGEBRA, "test_type": "end_of_course", "length": 30},
    ).json()
    assert [s["count"] for s in mid["shares"]] == [5, 4, 8, 3, 5, 5]  # units 1–6
    assert [s["count"] for s in eoc["shares"]] == [8, 5, 7, 6, 4]  # units 7–11
    assert {s["label"] for s in mid["shares"]}.isdisjoint(
        {s["label"] for s in eoc["shares"]}
    )


def test_generate_quiz_inline_manifest_with_gate(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "manifest": MANIFEST,
            "test_type": "unit_quiz",
            "length": 10,
            "kc_tag": "KC",
            "binding": "fixed_form",
            "pool_id": "small_2pl",
            "cognitive_profile": {
                "dimension": "bloom_process",
                # demo pool Bloom values are lowercase; profile values are the pinned
                # contract's — the gate should therefore flag them as unavailable
                "distribution": {"Apply": 0.5, "Analyze": 0.5},
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["feasibility_checked"] is True
    assert [s["count"] for s in body["shares"]] == [6, 4]
    # KC cells are satisfiable; the bloom_process marginals are not in this pool
    keys = {i["constraint_key"] for i in body["issues"]}
    assert keys == {"bloom_process=Apply", "bloom_process=Analyze"}
    assert body["feasible"] is False


def test_generate_validation_errors(client: TestClient) -> None:
    # unknown cognitive dimension -> 422 (pinned contract)
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "manifest": MANIFEST,
            "test_type": "unit_quiz",
            "length": 10,
            "cognitive_profile": {"dimension": "dok", "distribution": {"1": 1.0}},
        },
    )
    assert resp.status_code == 422

    # LOFT (unit-quiz default) target without tolerance -> 422 (§4.1)
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "manifest": MANIFEST,
            "test_type": "unit_quiz",
            "length": 10,
            "statistical_target": {"theta_points": [0], "target_info": [5]},
        },
    )
    assert resp.status_code == 422
    assert "tolerance" in resp.json()["detail"]

    # unknown scope unit -> 422
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "manifest": MANIFEST,
            "test_type": "cumulative_final",
            "scope_unit_ids": ["ghost"],
            "length": 10,
        },
    )
    assert resp.status_code == 422

    # exactly one curriculum source
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={"manifest": MANIFEST, "course_id": PRE_ALGEBRA, "length": 10},
    )
    assert resp.status_code == 422
    resp = client.post("/api/v1/blueprints/generate", json={"length": 10})
    assert resp.status_code == 422

    # unknown catalog course -> 404; unknown pool -> 404
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={"course_id": "ghost", "length": 10},
    )
    assert resp.status_code == 404
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "manifest": MANIFEST,
            "test_type": "unit_quiz",
            "length": 10,
            "pool_id": "nope",
        },
    )
    assert resp.status_code == 404
