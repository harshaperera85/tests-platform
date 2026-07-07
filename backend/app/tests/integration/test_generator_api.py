"""POST /blueprints/generate — curriculum→blueprint generator endpoint (§6)."""

from __future__ import annotations

from fastapi.testclient import TestClient

# A payload shaped exactly like the item-factory unit JSON export, including the
# extra complicator keys (examples/misconceptions) the schema must tolerate.
UNIT_DOC = {
    "course_id": "36e3fbed-0000-0000-0000-000000000001",
    "course_name": "Pre-Algebra Demo",
    "unit_id": "unit-9",
    "unit_order": 9,
    "unit_name": "Exponents",
    "knowledge_components": [
        {
            "id": "algebra",
            "order": 1,
            "name": "Product rule for exponents",
            "complicators": [
                {"id": "c1", "order": 1, "name": "like bases",
                 "examples": "x·x·x", "misconceptions": "- exponents multiply"},
                {"id": "c2", "order": 2, "name": "coefficients"},
                {"id": "c3", "order": 3, "name": "negative exponents"},
            ],
        },
        {
            "id": "number",
            "order": 2,
            "name": "Power of a power",
            "complicators": [
                {"id": "c4", "order": 1, "name": "nested"},
                {"id": "c5", "order": 2, "name": "mixed"},
            ],
        },
    ],
}


def test_generate_quiz_with_feasibility(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "units": [UNIT_DOC],
            "grain": "unit",
            "length": 10,
            "kc_tag": "KC",
            "pool_id": "small_2pl",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["feasibility_checked"] is True
    assert body["feasible"] is True and body["issues"] == []
    # weights 4 and 3 over length 10 -> 6 and 4
    assert [(s["key"], s["count"]) for s in body["shares"]] == [
        ("algebra", 6),
        ("number", 4),
    ]
    bp = body["blueprint"]
    assert bp["schema_version"] == 2
    assert bp["statistical_target"] is None  # content-only default
    assert any("feasibility-only" in w for w in body["warnings"])
    # the generated blueprint round-trips through the create endpoint
    created = client.post("/api/v1/blueprints", json=bp)
    assert created.status_code == 201, created.text


def test_generate_course_grain_infeasible_flagged(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "units": [UNIT_DOC],
            "grain": "course",
            "length": 10,
            "pool_id": "small_2pl",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # demo pool has no 'unit' tag dimension -> gate flags, does not error
    assert body["feasibility_checked"] is True
    assert body["feasible"] is False
    assert body["issues"][0]["available"] == 0


def test_generate_validation_errors(client: TestClient) -> None:
    # LOFT target without tolerance -> 422 (BP-MODES-1 §4.1)
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={
            "units": [UNIT_DOC],
            "grain": "unit",
            "length": 10,
            "binding": "loft",
            "statistical_target": {"theta_points": [0], "target_info": [5]},
        },
    )
    assert resp.status_code == 422
    assert "tolerance" in resp.json()["detail"]

    # unknown pool -> 404
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={"units": [UNIT_DOC], "grain": "unit", "length": 10, "pool_id": "nope"},
    )
    assert resp.status_code == 404

    # unknown unit_id -> 422
    resp = client.post(
        "/api/v1/blueprints/generate",
        json={"units": [UNIT_DOC], "grain": "unit", "unit_id": "missing", "length": 10},
    )
    assert resp.status_code == 422
