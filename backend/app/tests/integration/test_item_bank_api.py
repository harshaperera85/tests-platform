"""Item-bank import API + the end-to-end join: imported real-UUID items are
assembled by a curriculum-generated blueprint with zero mapping (backlog #9)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.psychometrics import pools
from app.services import item_bank as svc
from app.tests.util_item_bank import (
    PRE_ALGEBRA_COURSE,
    build_calibrated_export,
    build_stage_a_export,
    exponents_unit,
)


@pytest.fixture
def banks_dir(tmp_path, monkeypatch):
    d = tmp_path / "item_banks"
    monkeypatch.setattr(svc, "BANKS_DIR", d)
    monkeypatch.setattr(pools, "IMPORTED_BANKS_DIR", d)
    return d


def test_import_list_and_pool_endpoints(client: TestClient, banks_dir) -> None:
    resp = client.post("/api/v1/item-bank/import", json=build_calibrated_export())
    assert resp.status_code == 200, resp.text
    report = resp.json()
    assert report["n_administrable"] == 20 and report["pool_id"] == "pa-field-1"

    banks = client.get("/api/v1/item-bank").json()
    assert [b["bank_id"] for b in banks] == ["pa-field-1"]

    catalog = client.get("/api/v1/pool/catalog").json()
    assert any(p["pool_id"] == "pa-field-1" for p in catalog["pools"])

    items = client.get("/api/v1/pool/items", params={"pool_id": "pa-field-1"}).json()
    assert items["n_items"] == 20
    assert items["simulated"] is False
    # R3 join keys present on the served items
    assert {"unit", "kc"} <= set(items["items"][0]["tags"])


def test_import_validation_errors(client: TestClient, banks_dir) -> None:
    raw = build_calibrated_export()
    raw["metric"] = None
    resp = client.post("/api/v1/item-bank/import", json=raw)
    assert resp.status_code == 422 and "metric" in resp.json()["detail"]

    raw = build_calibrated_export()
    raw["items"][1]["instance_id"] = raw["items"][0]["instance_id"]
    assert client.post("/api/v1/item-bank/import", json=raw).status_code == 422


def test_stage_a_import_is_record_only(client: TestClient, banks_dir) -> None:
    resp = client.post("/api/v1/item-bank/import", json=build_stage_a_export())
    assert resp.status_code == 200
    report = resp.json()
    assert report["n_administrable"] == 0 and report["pool_id"] is None
    assert any("PRE-EPOCH" in w for w in report["warnings"])
    catalog = client.get("/api/v1/pool/catalog").json()
    assert not any(p["pool_id"] == "pa-authoring-1" for p in catalog["pools"])


def test_generated_blueprint_assembles_imported_items(
    client: TestClient, banks_dir
) -> None:
    """The join this whole seam exists for: a blueprint generated from the real
    curriculum (kc cells keyed on UUIDs) assembles a form from imported items
    tagged with the same UUIDs — no mapping layer anywhere."""
    assert (
        client.post(
            "/api/v1/item-bank/import", json=build_calibrated_export()
        ).status_code
        == 200
    )

    unit = exponents_unit()
    gen = client.post(
        "/api/v1/blueprints/generate",
        json={
            "course_id": PRE_ALGEBRA_COURSE,
            "test_type": "unit_quiz",
            "unit_id": unit.unit_id,
            "length": 8,
            "binding": "fixed_form",  # count cells for exact-allocation assertion
            "pool_id": "pa-field-1",
        },
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert body["feasibility_checked"] and body["feasible"], body["issues"]
    shares = {s["key"]: s["count"] for s in body["shares"]}
    assert sum(shares.values()) == 8

    bid = client.post("/api/v1/blueprints", json=body["blueprint"]).json()["id"]
    job = client.post(
        "/api/v1/assembly-jobs",
        json={
            "blueprint_id": bid,
            "pool_id": "pa-field-1",
            "strategy": "mip",
            "time_limit_s": 8,
        },
    )
    assert job.status_code == 201, job.text
    jbody = job.json()
    assert jbody["status"] in ("optimal", "feasible")

    form = client.get(f"/api/v1/forms/{jbody['form_ids'][0]}").json()
    assert len(form["item_ids"]) == 8
    # every assembled item is an imported one, and per-KC counts match the
    # largest-remainder allocation exactly
    pool_items = client.get(
        "/api/v1/pool/items", params={"pool_id": "pa-field-1"}
    ).json()["items"]
    kc_of = {it["item_id"]: it["tags"]["kc"] for it in pool_items}
    assert all(iid in kc_of for iid in form["item_ids"])
    for kc_id, want in shares.items():
        got = sum(1 for iid in form["item_ids"] if kc_of[iid] == kc_id)
        assert got == want, (kc_id, got, want)
