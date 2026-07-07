"""POST /blueprints/generate + GET /curricula — §6 generator endpoints."""

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


def test_generate_eoc_from_catalog_course(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={"course_id": PRE_ALGEBRA, "grain": "eoc", "length": 60},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [s["count"] for s in body["shares"]] == [6, 5, 9, 4, 6, 6, 6, 4, 6, 5, 3]
    bp = body["blueprint"]
    assert bp["schema_version"] == 2
    assert bp["statistical_target"] is None
    assert all(c["mode"] == "count" for c in bp["content_constraints"])
    assert body["feasibility_checked"] is False  # no pool_id supplied
    # not auto-saved: the blueprint round-trips through explicit create
    created = client.post("/api/v1/blueprints", json=bp)
    assert created.status_code == 201, created.text


def test_generate_quiz_inline_manifest_with_gate(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "manifest": MANIFEST,
            "grain": "unit_quiz",
            "length": 10,
            "kc_tag": "KC",
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
            "length": 10,
            "cognitive_profile": {"dimension": "dok", "distribution": {"1": 1.0}},
        },
    )
    assert resp.status_code == 422

    # LOFT target without tolerance -> 422 (§4.1)
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "manifest": MANIFEST,
            "length": 10,
            "binding": "loft",
            "statistical_target": {"theta_points": [0], "target_info": [5]},
        },
    )
    assert resp.status_code == 422
    assert "tolerance" in resp.json()["detail"]

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
        json={"manifest": MANIFEST, "length": 10, "pool_id": "nope"},
    )
    assert resp.status_code == 404
