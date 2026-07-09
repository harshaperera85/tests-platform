"""Field-study assembly path: content-only forms from uncalibrated items —
the calibration bootstrap's missing middle (import → field pool → field form)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.assembly import assemble, compile_blueprint
from app.psychometrics import pools
from app.schemas.blueprint import Blueprint, ContentConstraint, TIFTarget
from app.schemas.item_bank import ItemBankExportIn
from app.services import item_bank as svc
from app.services.item_bank import ingest_export
from app.tests.util_item_bank import (
    PRE_ALGEBRA_COURSE,
    build_field_study_export,
    exponents_unit,
)


@pytest.fixture
def banks_dir(tmp_path, monkeypatch):
    d = tmp_path / "item_banks"
    monkeypatch.setattr(svc, "BANKS_DIR", d)
    monkeypatch.setattr(pools, "IMPORTED_BANKS_DIR", d)
    return d


def _import_field_bank() -> str:
    report = ingest_export(ItemBankExportIn.model_validate(build_field_study_export()))
    assert report.n_field_eligible == 20  # 16 pilots + 4 live anchors
    assert report.n_administrable == 4  # only the calibrated live anchors
    assert report.field_pool_id == "pa-pilot-1-field"
    return report.field_pool_id  # type: ignore[return-value]


# --------------------------------------------------------------- pool layer
def test_field_pool_loads_and_is_content_only(banks_dir) -> None:
    fid = _import_field_bank()
    assert pools.is_field_pool(fid)
    fp = pools.load_assembly_pool(fid)
    assert len(fp.items) == 20
    anchors = [it for it in fp.items if it.calibrated]
    assert len(anchors) == 4  # anchors flagged, but NO parameters exposed
    assert not hasattr(fp.items[0], "a")
    # the parametric loader refuses field pools loudly
    with pytest.raises(ValueError, match="content-only"):
        pools.load_pool_by_id(fid)


# ----------------------------------------------------------------- assembly
def test_field_assembly_content_only(banks_dir) -> None:
    fid = _import_field_bank()
    fp = pools.load_assembly_pool(fid)
    unit = exponents_unit()
    bp = Blueprint(
        name="field-form",
        length=10,
        content_constraints=[
            ContentConstraint(tag_type="kc", tag_value=kc.kc_id, minimum=2)
            for kc in unit.kcs
        ],
    )
    problem = compile_blueprint(bp, fp)
    assert problem.feasibility_only and problem.theta_points == ()
    assert problem.params == ()

    for strategy in ("mip", "random_constrained"):
        result = assemble(bp, fp, strategy=strategy, time_limit_s=5)
        assert result.feasible, strategy
        form = result.forms[0]
        assert len(form.item_ids) == 10
        assert form.tif_actual == []  # honestly absent, not fabricated
        kc_counts: dict[str, int] = {}
        for iid in form.item_ids:
            kc = fp.get(iid).tags["kc"]
            kc_counts[kc] = kc_counts.get(kc, 0) + 1
        assert all(v >= 2 for v in kc_counts.values())


def test_field_pool_rejects_tif_target(banks_dir) -> None:
    fid = _import_field_bank()
    fp = pools.load_assembly_pool(fid)
    bp = Blueprint(
        length=5,
        statistical_target=TIFTarget(theta_points=[0.0], target_info=[5.0]),
    )
    with pytest.raises(ValueError, match="content-only"):
        compile_blueprint(bp, fp)


# ------------------------------------------------------------------ API e2e
def test_field_study_end_to_end(client: TestClient, banks_dir) -> None:
    """Import mixed bank → field pool in catalog → content-only generated
    blueprint gated against it → assembled field form → degraded reporting."""
    resp = client.post("/api/v1/item-bank/import", json=build_field_study_export())
    assert resp.status_code == 200
    body = resp.json()
    assert body["field_pool_id"] == "pa-pilot-1-field"

    # catalog lists BOTH derivations: anchors pool + field pool
    catalog = client.get("/api/v1/pool/catalog").json()
    ids = {p["pool_id"] for p in catalog["pools"]}
    assert {"pa-pilot-1", "pa-pilot-1-field"} <= ids

    # pool viewer serves paramless items honestly
    items = client.get(
        "/api/v1/pool/items", params={"pool_id": "pa-pilot-1-field"}
    ).json()
    assert items["pool_kind"] == "field" and items["n_items"] == 20
    assert items["items"][0]["a"] is None and items["items"][0]["b"] is None
    assert "kc" in items["tag_summary"]

    # generate a content-only quiz blueprint gated against the FIELD pool
    unit = exponents_unit()
    gen = client.post(
        "/api/v1/blueprints/generate",
        json={
            "course_id": PRE_ALGEBRA_COURSE,
            "test_type": "unit_quiz",
            "unit_id": unit.unit_id,
            "length": 8,
            "binding": "fixed_form",
            "pool_id": "pa-pilot-1-field",
        },
    )
    assert gen.status_code == 200, gen.text
    gbody = gen.json()
    assert gbody["feasible"], gbody["issues"]
    assert gbody["blueprint"]["statistical_target"] is None

    # assemble the field form through the real job path
    bid = client.post("/api/v1/blueprints", json=gbody["blueprint"]).json()["id"]
    job = client.post(
        "/api/v1/assembly-jobs",
        json={
            "blueprint_id": bid,
            "pool_id": "pa-pilot-1-field",
            "strategy": "mip",
            "time_limit_s": 8,
        },
    )
    assert job.status_code == 201, job.text
    jbody = job.json()
    assert jbody["status"] in ("optimal", "feasible")
    form_id = jbody["form_ids"][0]

    form = client.get(f"/api/v1/forms/{form_id}").json()
    assert len(form["item_ids"]) == 8
    assert form["tif"] == []  # no target, no params — nothing to plot

    # degraded-but-honest reporting on field forms
    qa = client.get(f"/api/v1/forms/{form_id}/qa-report").json()
    assert qa["marginal_reliability"] is None and qa["curve"] == []
    assert len(qa["answer_key"]) == 8
    assert all(row["satisfied"] for row in qa["coverage"])

    curve = client.get(f"/api/v1/forms/{form_id}/tif-curve").json()
    assert curve["curve"] == [] and curve["method"] == "none"

    sim = client.get(f"/api/v1/forms/{form_id}/simulate")
    assert sim.status_code == 422 and "uncalibrated" in sim.json()["detail"]

    cmp_resp = client.post(
        "/api/v1/forms/compare", json={"form_ids": [form_id, form_id]}
    )
    assert cmp_resp.status_code == 422

    walk = client.post(
        "/api/v1/preview/walkthrough", json={"pool_id": "pa-pilot-1-field"}
    )
    assert walk.status_code in (404, 422)  # guarded (path shape may differ)
