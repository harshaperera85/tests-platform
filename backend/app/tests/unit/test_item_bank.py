"""Item-bank importer (backlog #9): validation, normalization, two-axis
derivation, identity-epoch policy, catalog integration."""

from __future__ import annotations

import pytest

from app.psychometrics import pools
from app.schemas.item_bank import ItemBankExportIn
from app.services import item_bank as svc
from app.services.item_bank import BankIngestError, ingest_export, list_banks
from app.tests.util_item_bank import build_calibrated_export, build_stage_a_export


@pytest.fixture
def banks_dir(tmp_path, monkeypatch):
    d = tmp_path / "item_banks"
    monkeypatch.setattr(svc, "BANKS_DIR", d)
    monkeypatch.setattr(pools, "IMPORTED_BANKS_DIR", d)
    return d


def _doc(raw: dict) -> ItemBankExportIn:
    return ItemBankExportIn.model_validate(raw)


# ------------------------------------------------------------- contract shape
def test_fixture_exports_satisfy_the_pinned_contract() -> None:
    """The seam contract test: both shaped fixtures validate as export docs,
    instance_id aliases to item_id verbatim, R3 tag keys present."""
    cal = _doc(build_calibrated_export())
    assert cal.items[0].item_id == "pa-field-1-it001"  # instance_id alias, verbatim
    assert {"domain", "unit", "kc", "complicator", "bloom_process",
            "bloom_knowledge", "timss"} <= set(cal.items[0].tags)
    stage_a = _doc(build_stage_a_export())
    assert not stage_a.items[0].has_params


# ------------------------------------------------------------------ happy path
def test_ingest_calibrated_bank(banks_dir) -> None:
    report = ingest_export(_doc(build_calibrated_export()))
    assert report.n_items == 20
    assert report.n_administrable == 20
    assert report.pool_id == "pa-field-1"
    assert report.editorial_counts == {"live": 20}
    assert report.calibration_counts == {"field_calibrated": 20}
    assert not any("PRE-EPOCH" in w for w in report.warnings)
    assert (banks_dir / "pa-field-1" / "bank.json").is_file()
    assert (banks_dir / "pa-field-1" / "pool.json").is_file()

    # catalog + loader integration: the derived pool is a first-class pool
    assert pools.is_known("pa-field-1")
    assert any(e.pool_id == "pa-field-1" for e in pools.catalog())
    pool = pools.load_pool_by_id("pa-field-1")
    assert len(pool.items) == 20
    it = pool.get("pa-field-1-it002")
    assert it.enemy_of == ("pa-field-1-it001",)  # structured refs -> bare ids
    assert it.a > 0 and it.tags["kc"]

    assert list_banks()[0].n_administrable == 20


def test_stage_a_bank_is_record_only(banks_dir) -> None:
    report = ingest_export(_doc(build_stage_a_export()))
    assert report.n_items == 10
    assert report.n_administrable == 0
    assert report.pool_id is None
    assert report.calibration_counts == {"uncalibrated": 10}
    assert any("PRE-EPOCH" in w for w in report.warnings)
    assert any("no administrable items" in w for w in report.warnings)
    assert (banks_dir / "pa-authoring-1" / "bank.json").is_file()
    assert not (banks_dir / "pa-authoring-1" / "pool.json").exists()
    assert not pools.is_known("pa-authoring-1")


# -------------------------------------------------------------- rule 4: metric
def test_params_without_metric_rejected(banks_dir) -> None:
    raw = build_calibrated_export()
    raw["metric"] = None
    with pytest.raises(BankIngestError, match="metric"):
        ingest_export(_doc(raw))
    assert not (banks_dir / "pa-field-1").exists()  # nothing persisted


def test_difficulty_form_rejected(banks_dir) -> None:
    raw = build_calibrated_export()
    raw["metric"]["form"] = "difficulty"
    with pytest.raises(BankIngestError, match="slope_intercept"):
        ingest_export(_doc(raw))


def test_cross_scale_params_normalized(banks_dir) -> None:
    """A D=1.702 export rescales (a, d) jointly onto D=1; b is invariant."""
    raw = build_calibrated_export(bank_id="pa-ogive")
    raw["metric"]["scaling_d"] = 1.702
    src = raw["items"][0]
    report = ingest_export(_doc(raw))
    assert report.n_administrable == 20
    pool = pools.load_pool_by_id("pa-ogive")
    it = pool.get(src["instance_id"])
    assert it.a == pytest.approx(src["a"] * 1.702)
    assert it.d == pytest.approx(src["d"] * 1.702)
    assert it.b == pytest.approx(-src["d"] / src["a"])  # difficulty view invariant
    assert it.scaling_d == 1.0


# ------------------------------------------------------------- fatal validation
def test_duplicate_ids_rejected(banks_dir) -> None:
    raw = build_calibrated_export()
    raw["items"][1]["instance_id"] = raw["items"][0]["instance_id"]
    with pytest.raises(BankIngestError, match="duplicate"):
        ingest_export(_doc(raw))


def test_partial_params_rejected(banks_dir) -> None:
    raw = build_calibrated_export()
    raw["items"][0]["d"] = None
    with pytest.raises(BankIngestError, match="partial"):
        ingest_export(_doc(raw))


def test_nonpositive_a_rejected(banks_dir) -> None:
    raw = build_calibrated_export()
    raw["items"][0]["a"] = 0.0
    with pytest.raises(BankIngestError, match="a <= 0"):
        ingest_export(_doc(raw))


def test_reserved_bank_id_rejected(banks_dir) -> None:
    raw = build_calibrated_export(bank_id="small_2pl")
    with pytest.raises(BankIngestError, match="shadows"):
        ingest_export(_doc(raw))


# ------------------------------------------------------------ quality warnings
def test_off_contract_cognitive_values_warn(banks_dir) -> None:
    raw = build_calibrated_export()
    for it in raw["items"][:6]:
        it["tags"]["bloom_process"] = "apply"  # lowercase = off the pinned contract
    report = ingest_export(_doc(raw))
    assert any("off the pinned contract" in w for w in report.warnings)


def test_reimport_content_hash_change_flagged(banks_dir) -> None:
    ingest_export(_doc(build_calibrated_export()))
    raw = build_calibrated_export()
    raw["items"][0]["content_hash"] = "sha256:DIFFERENT"
    report = ingest_export(_doc(raw))
    assert any("IDENTITY-CONTRACT VIOLATION" in w for w in report.warnings)


def test_reimport_can_withdraw_pool(banks_dir) -> None:
    ingest_export(_doc(build_calibrated_export()))
    assert pools.is_known("pa-field-1")
    raw = build_calibrated_export()
    for it in raw["items"]:
        it["status"] = "quarantined"
    report = ingest_export(_doc(raw))
    assert report.n_administrable == 0
    assert any("withdrawn" in w for w in report.warnings)
    assert not pools.is_known("pa-field-1")


# ---------------------------------------------------- two-axis administrability
@pytest.mark.parametrize(
    ("editorial", "calibration", "administrable"),
    [
        ("live", "field_calibrated", True),
        ("live", "provisional", False),
        ("live", "uncalibrated", False),
        ("pilot", "field_calibrated", False),
        ("quarantined", "field_calibrated", False),
    ],
)
def test_administrability_is_derived_from_both_axes(
    banks_dir, editorial: str, calibration: str, administrable: bool
) -> None:
    raw = build_calibrated_export(bank_id="pa-axes")
    for it in raw["items"]:
        it["status"] = editorial
        it["calibration_status"] = calibration
        if calibration == "uncalibrated":
            it["a"] = it["d"] = it["c"] = it["u"] = None
            it["se_a"] = it["se_d"] = it["cov_ad"] = None
    if all(it["a"] is None for it in raw["items"]):
        raw["metric"] = None
    report = ingest_export(_doc(raw))
    assert (report.n_administrable > 0) is administrable
