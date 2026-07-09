"""Item-bank importer (backlog #9) — the real item-data swap point.

Ingests an item-factory CAT-ready export (the pinned contract,
`docs/item_factory_seam_investigation.md` §7), validates it, normalizes parameters
to the canonical metric, and persists TWO artifacts per bank under
``app/data/item_banks/<bank_id>/``:

- ``bank.json`` — the normalized **superset** record: every item, both status axes,
  nullable IRT. The bank of record for viewers and future write-back.
- ``pool.json`` — the derived **administrable pool** in the platform's standard
  pool-document format, so the existing catalog/loader machinery (and therefore the
  blueprint editor, assembly engine, worker, QA, …) consumes imported items with
  zero changes at the 16 existing call sites. Only written when something is
  administrable.

**Administrability is DERIVED, never stored** (two-axis design):
``editorial status ∈ ADMINISTRABLE_EDITORIAL`` AND
``calibration status ∈ ADMINISTRABLE_CALIBRATION`` AND parameters present.
An uncalibrated Stage-A bank imports cleanly (bank of record) but yields no
assembly pool — that is correct behavior, not an error.

**Identity epoch** (R4): exports without content hashes are pre-epoch — imported
with a prominent warning that their ids must not be used as calibration join keys.
On re-import of the same bank, a changed hash under an unchanged id is reported —
that is the contract violation the hash exists to catch.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.psychometrics.params import (
    CANONICAL_FORM,
    ItemParameters,
    normalize_to_canonical,
    require_metric,
)
from app.schemas.generator import COGNITIVE_DIMENSIONS
from app.schemas.item_bank import (
    ADMINISTRABLE_CALIBRATION,
    ADMINISTRABLE_EDITORIAL,
    BankIngestReport,
    BankItemIn,
    BankSummary,
    ItemBankExportIn,
)

#: On-disk home for imported banks (runtime artifacts — gitignored).
BANKS_DIR = Path(__file__).parent.parent / "data" / "item_banks"

#: Fixture pool ids that imports may never shadow.
_RESERVED_POOL_IDS = frozenset({"small_2pl", "demo_mixed"})


class BankIngestError(ValueError):
    """Fatal ingest problem — nothing was persisted."""


def _derived_calibration_status(item: BankItemIn, metric_kind: str | None) -> str:
    if item.calibration_status is not None:
        return item.calibration_status
    if not item.has_params:
        return "uncalibrated"
    return "field_calibrated" if metric_kind == "calibrated" else "provisional"


def _normalize_options(options: list | None) -> list[dict]:
    """Map exported options onto the platform's ``{key, text}`` shape.

    Accepts bare strings (keyed A, B, C, …), ``{key, text}`` dicts (verbatim), or
    other dicts (best-effort text extraction) — display content only, never
    load-bearing for assembly."""
    if not options:
        return []
    out: list[dict] = []
    for i, opt in enumerate(options):
        key = chr(ord("A") + i)
        if isinstance(opt, dict):
            out.append(
                {
                    "key": str(opt.get("key", key)),
                    "text": str(opt.get("text", opt.get("label", opt))),
                }
            )
        else:
            out.append({"key": key, "text": str(opt)})
    return out


def _is_administrable(editorial: str, calibration: str, has_params: bool) -> bool:
    return (
        editorial in ADMINISTRABLE_EDITORIAL
        and calibration in ADMINISTRABLE_CALIBRATION
        and has_params
    )


def _validate(doc: ItemBankExportIn) -> list[str]:
    """Fatal checks (raise) + returns non-fatal warnings."""
    warnings: list[str] = []

    if doc.bank_id in _RESERVED_POOL_IDS:
        raise BankIngestError(f"bank_id {doc.bank_id!r} shadows a fixture pool id")

    counts = Counter(i.item_id for i in doc.items)
    dups = sorted(k for k, n in counts.items() if n > 1)
    if dups:
        raise BankIngestError(f"duplicate item ids in export: {dups[:5]}")

    partial = [
        i.item_id for i in doc.items if (i.a is None) != (i.d is None)
    ]
    if partial:
        raise BankIngestError(
            f"items with partial parameters (a xor d): {partial[:5]} — a calibrated "
            "item carries both, an uncalibrated item carries neither"
        )
    bad_a = [i.item_id for i in doc.items if i.a is not None and i.a <= 0]
    if bad_a:
        raise BankIngestError(f"items with a <= 0: {bad_a[:5]}")

    # identity epoch (R4)
    n_hashed = sum(1 for i in doc.items if i.content_hash)
    if n_hashed == 0:
        warnings.append(
            "PRE-EPOCH EXPORT: no content hashes present — item ids are not "
            "calibration-stable until the item-factory regeneration campaign "
            "(identity epoch); do NOT use these ids as calibration join keys."
        )
    elif n_hashed < len(doc.items):
        warnings.append(
            f"{len(doc.items) - n_hashed} of {len(doc.items)} items lack a "
            "content_hash — mixed-epoch export; verify upstream."
        )

    # R3 tag expectations (warn, never reject — imported data reality)
    n_no_join = sum(
        1 for i in doc.items if "unit" not in i.tags or "kc" not in i.tags
    )
    if n_no_join:
        warnings.append(
            f"{n_no_join} item(s) missing unit/kc tags — they cannot join "
            "curriculum-generated blueprints."
        )
    off_contract: Counter[str] = Counter()
    for i in doc.items:
        for dim, allowed in COGNITIVE_DIMENSIONS.items():
            v = i.tags.get(dim)
            if v is not None and v not in allowed:
                off_contract[f"{dim}={v}"] += 1
    if off_contract:
        sample = ", ".join(f"{k} ({n}×)" for k, n in off_contract.most_common(3))
        warnings.append(
            f"cognitive tag values off the pinned contract: {sample} — these will "
            "not match authored cognitive profiles."
        )

    known_ids = {i.item_id for i in doc.items}
    n_external = sum(
        1 for i in doc.items for e in i.enemy_ids if e not in known_ids
    )
    if n_external:
        warnings.append(
            f"{n_external} enemy reference(s) point outside this export — "
            "kept verbatim; they bind only if those items are imported too."
        )
    return warnings


def ingest_export(
    doc: ItemBankExportIn, *, banks_dir: Path | None = None
) -> BankIngestReport:
    """Validate, normalize, persist; returns the ingest report.

    Raises :class:`BankIngestError` (nothing persisted) on fatal problems,
    including a golden-rule-4 violation: parameters present without a declared
    metric.
    """
    base = banks_dir if banks_dir is not None else BANKS_DIR
    warnings = _validate(doc)

    # ---- metric (rule 4): required iff any item carries parameters ---------
    any_params = any(i.has_params for i in doc.items)
    metric = None
    if any_params:
        try:
            metric = require_metric(doc.metric, where=f"bank {doc.bank_id!r}")
        except ValueError as exc:
            raise BankIngestError(str(exc)) from exc
        if metric.form != CANONICAL_FORM:
            raise BankIngestError(
                f"bank {doc.bank_id!r} declares form {metric.form!r}; ingest "
                "accepts slope_intercept only (convert difficulty-form params "
                "upstream via scoring-r /convert-difficulty)"
            )
    metric_kind = metric.kind if metric is not None else None

    # ---- re-import hash check (identity contract) --------------------------
    bank_path = base / doc.bank_id / "bank.json"
    if bank_path.is_file():
        old = json.loads(bank_path.read_text())
        old_hashes = {
            it["item_id"]: it.get("content_hash")
            for it in old.get("items", [])
            if it.get("content_hash")
        }
        changed = [
            i.item_id
            for i in doc.items
            if i.content_hash
            and old_hashes.get(i.item_id)
            and old_hashes[i.item_id] != i.content_hash
        ]
        if changed:
            warnings.append(
                f"IDENTITY-CONTRACT VIOLATION on re-import: {len(changed)} item "
                f"id(s) kept their id but changed content hash (e.g. "
                f"{changed[:3]}) — an id must never denote different content. "
                "Imported as given; raise with item-factory."
            )

    # ---- normalize + partition ---------------------------------------------
    bank_items: list[dict] = []
    pool_items: list[dict] = []
    editorial_counts: Counter[str] = Counter()
    calibration_counts: Counter[str] = Counter()

    for item in doc.items:
        calibration = _derived_calibration_status(item, metric_kind)
        editorial_counts[item.status] += 1
        calibration_counts[calibration] += 1

        a, d, c, u = item.a, item.d, item.c, item.u
        if item.has_params and metric is not None:
            params = normalize_to_canonical(
                ItemParameters(
                    item_id=item.item_id,
                    a=float(item.a),  # type: ignore[arg-type]
                    d=float(item.d),  # type: ignore[arg-type]
                    c=item.c if item.c is not None else 0.0,
                    u=item.u if item.u is not None else 1.0,
                    scaling_d=metric.scaling_d,
                    se_a=item.se_a,
                    se_d=item.se_d,
                    cov_ad=item.cov_ad,
                    se_b=item.se_b,
                )
            )
            a, d, c, u = params.a, params.d, params.c, params.u

        record = {
            "item_id": item.item_id,
            "template_id": item.template_id,
            "radical_config": item.radical_config,
            "content_hash": item.content_hash,
            "editorial_status": item.status,
            "calibration_status": calibration,
            "tags": item.tags,
            "enemy_of": item.enemy_ids,
            "stem": item.stem,
            "options": item.options,
            "answer_key": item.answer_key,
            "a": a, "d": d, "c": c, "u": u,
            "se_a": item.se_a, "se_d": item.se_d,
            "cov_ad": item.cov_ad, "se_b": item.se_b,
            "calibration": item.calibration,
        }
        bank_items.append(record)

        if _is_administrable(item.status, calibration, item.has_params):
            pool_items.append(
                {
                    "item_id": item.item_id,
                    "a": a, "d": d,
                    "c": c if c is not None else 0.0,
                    "u": u if u is not None else 1.0,
                    "b": -d / a,  # type: ignore[operator]
                    "tags": item.tags,
                    "enemy_of": item.enemy_ids,
                    "se_a": item.se_a, "se_d": item.se_d,
                    "stem": item.stem,
                    "options": _normalize_options(item.options),
                    "answer_key": (
                        str(item.answer_key) if item.answer_key is not None else None
                    ),
                }
            )

    imported_at = datetime.now(UTC).isoformat(timespec="seconds")
    bank_doc = {
        "bank_id": doc.bank_id,
        "imported_at": imported_at,
        "domain": doc.domain,
        "export_version": doc.export_version,
        "generated_at": doc.generated_at,
        "provenance": doc.provenance or "item-factory CAT-ready export",
        "metric": doc.metric,
        "n_items": len(bank_items),
        "n_administrable": len(pool_items),
        "editorial_counts": dict(editorial_counts),
        "calibration_counts": dict(calibration_counts),
        "items": bank_items,
    }

    bank_dir = base / doc.bank_id
    bank_dir.mkdir(parents=True, exist_ok=True)
    (bank_dir / "bank.json").write_text(json.dumps(bank_doc, indent=1) + "\n")

    pool_id: str | None = None
    pool_path = bank_dir / "pool.json"
    if pool_items:
        pool_doc = {
            "metric": {
                "model": "2PL/3PL",
                "scaling_d": 1.0,
                "form": "slope_intercept",
                "kind": metric_kind or "calibrated",
            },
            "simulated": False,
            "provenance": (
                f"administrable derivation of imported bank {doc.bank_id!r} "
                f"({imported_at}); editorial∈{sorted(ADMINISTRABLE_EDITORIAL)} ∧ "
                f"calibration∈{sorted(ADMINISTRABLE_CALIBRATION)}"
            ),
            "items": pool_items,
        }
        pool_path.write_text(json.dumps(pool_doc, indent=1) + "\n")
        pool_id = doc.bank_id
    elif pool_path.is_file():
        pool_path.unlink()  # re-import may have withdrawn administrability
        warnings.append(
            "re-import removed all administrable items; the derived pool was "
            "withdrawn from the catalog."
        )
    else:
        warnings.append(
            "no administrable items (need editorial 'live' + calibrated "
            "parameters) — bank imported as record only; no assembly pool derived."
        )

    return BankIngestReport(
        bank_id=doc.bank_id,
        n_items=len(bank_items),
        n_administrable=len(pool_items),
        editorial_counts=dict(editorial_counts),
        calibration_counts=dict(calibration_counts),
        pool_id=pool_id,
        warnings=warnings,
    )


def list_banks(*, banks_dir: Path | None = None) -> list[BankSummary]:
    base = banks_dir if banks_dir is not None else BANKS_DIR
    out: list[BankSummary] = []
    if not base.is_dir():
        return out
    for bank_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        path = bank_dir / "bank.json"
        if not path.is_file():
            continue
        doc = json.loads(path.read_text())
        out.append(
            BankSummary(
                bank_id=doc["bank_id"],
                imported_at=doc.get("imported_at"),
                domain=doc.get("domain"),
                export_version=doc.get("export_version"),
                n_items=doc.get("n_items", len(doc.get("items", []))),
                n_administrable=doc.get("n_administrable", 0),
                editorial_counts=doc.get("editorial_counts", {}),
                calibration_counts=doc.get("calibration_counts", {}),
                pool_id=doc["bank_id"] if (bank_dir / "pool.json").is_file() else None,
            )
        )
    return out
