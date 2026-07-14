"""Shaped item-bank export builders for importer tests (backlog #9).

Builds export documents in the pinned contract shape using the REAL pre-algebra
curriculum ids (unit/kc/complicator UUIDs from the shipped catalog), so the
generator→importer join is exercised with the exact identifiers both sides will
share in production. Deterministic — no randomness.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services import curricula

BLOOM_PROCESS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
BLOOM_KNOWLEDGE = ["Factual", "Conceptual", "Procedural", "Metacognitive"]
TIMSS = ["Knowing", "Applying", "Reasoning"]

PRE_ALGEBRA_COURSE = "36e3fbed-61f1-4454-a41c-93e665bb1715"


def exponents_unit():
    manifest = curricula.get_manifest(PRE_ALGEBRA_COURSE)
    assert manifest is not None
    return next(u for u in manifest.units if u.name == "Exponents")


def contract_content_hash(stem: str, options: list, key: str) -> str:
    """The export-contract §2 hash: sha256 hex over canonical JSON of
    {key, options, stem} — sorted keys, compact separators, ensure_ascii=false."""
    canonical = json.dumps(
        {"key": key, "options": options, "stem": stem},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_calibrated_export(
    bank_id: str = "pa-field-1", items_per_kc: int = 4
) -> dict[str, Any]:
    """A post-epoch, field-calibrated export over the real Exponents unit:
    ``items_per_kc`` live items per KC, complicators round-robined (≤2 per
    complicator at the default size), structured enemy pairs, content hashes."""
    unit = exponents_unit()
    items: list[dict[str, Any]] = []
    n = 0
    for kc in unit.kcs:
        comp_ids = [c.id for c in kc.complicators if c.id]
        for j in range(items_per_kc):
            n += 1
            a = 0.8 + 0.05 * (n % 12)
            b = -1.5 + 0.15 * (n % 20)
            items.append(
                {
                    "instance_id": f"{bank_id}-it{n:03d}",
                    "template_id": f"tmpl-{kc.kc_id[:8]}-{j % max(len(comp_ids), 1)}",
                    "radical_config": {"slot": j},
                    # real contract-§2 hash (computed below, needs stem/options/key)
                    "content_hash": None,
                    "status": "live",
                    "calibration_status": "field_calibrated",
                    "stem": f"Item {n} on {kc.name or kc.kc_id}",
                    "options": ["A", "B", "C", "D"],
                    "answer_key": "A",
                    "tags": {
                        "domain": "PA",
                        "unit": unit.unit_id,
                        "kc": kc.kc_id,
                        "complicator": comp_ids[j % len(comp_ids)]
                        if comp_ids
                        else "none",
                        "bloom_process": BLOOM_PROCESS[n % len(BLOOM_PROCESS)],
                        "bloom_knowledge": BLOOM_KNOWLEDGE[n % len(BLOOM_KNOWLEDGE)],
                        "timss": TIMSS[n % len(TIMSS)],
                    },
                    "enemy_of": (
                        [{"enemy_id": f"{bank_id}-it{n - 1:03d}",
                          "reasons": ["same stimulus"], "type": "clone"}]
                        if j == 1
                        else []
                    ),
                    "a": round(a, 4),
                    "d": round(-a * b, 4),
                    "c": 0.0,
                    "u": 1.0,
                    "se_a": 0.08,
                    "se_d": 0.1,
                    "cov_ad": 0.002,
                    "calibration": {"model": "2PL", "n": 1200, "date": "2026-07-01"},
                }
            )
    for it in items:  # post-epoch export: real contract-§2 hashes
        it["content_hash"] = contract_content_hash(
            it["stem"], it["options"], it["answer_key"]
        )
    return {
        "bank_id": bank_id,
        "export_version": 1,
        "domain": "PA",
        "generated_at": "2026-07-09T00:00:00Z",
        "metric": {"scaling_d": 1.0, "form": "slope_intercept", "kind": "calibrated"},
        "items": items,
    }


def build_stage_a_export(bank_id: str = "pa-authoring-1") -> dict[str, Any]:
    """A pre-epoch, pre-calibration (Stage A) export: content + tags + status,
    no parameters, no hashes — imports as record only."""
    doc = build_calibrated_export(bank_id=bank_id, items_per_kc=2)
    for it in doc["items"]:
        for k in ("a", "d", "c", "u", "se_a", "se_d", "cov_ad", "calibration",
                  "content_hash"):
            it[k] = None
        it["status"] = "in_review"
        it["calibration_status"] = "uncalibrated"
    doc["metric"] = None
    return doc


def build_field_study_export(bank_id: str = "pa-pilot-1") -> dict[str, Any]:
    """A mixed field-study bank over the real Exponents unit: mostly PILOT
    (uncalibrated) items plus a few LIVE calibrated anchors — the standard
    field-form design (pilots ride alongside anchors). Post-epoch hashes."""
    doc = build_calibrated_export(bank_id=bank_id, items_per_kc=4)
    for i, it in enumerate(doc["items"]):
        if i % 5 == 0:
            continue  # every 5th item stays a live, calibrated anchor
        it["status"] = "pilot"
        it["calibration_status"] = "uncalibrated"
        for k in ("a", "d", "c", "u", "se_a", "se_d", "cov_ad", "calibration"):
            it[k] = None
    return doc
