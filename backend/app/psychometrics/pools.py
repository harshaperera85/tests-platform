"""Catalog of selectable item pools (the plan's ``item_pool_ref``, §8).

Until the item-factory export is wired, the platform ships **simulated** banks so
every workflow is demonstrable end-to-end. Each pool is a calibrated bank file;
callers select one by ``pool_id``. The default stays the small smoke bank so
existing behavior/tests are unchanged; the UI defaults to the richer demo bank.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.psychometrics.bank import (
    FieldPool,
    ItemPool,
    load_bank_document,
    load_field_pool,
    load_pool,
)

_FIXTURES = Path(__file__).parent / "fixtures"

#: Default pool — the small 2PL smoke bank (stable for tests / existing callers).
DEFAULT_POOL_ID = "small_2pl"


@dataclass(frozen=True)
class PoolEntry:
    pool_id: str
    title: str
    description: str
    path: Path
    #: "parametric" (standard pool doc) or "field" (content-only field-study pool)
    kind: str = "parametric"


_CATALOG: dict[str, PoolEntry] = {
    "small_2pl": PoolEntry(
        pool_id="small_2pl",
        title="Small 2PL smoke bank",
        description="48 calibrated 2PL items — minimal fixture for quick checks.",
        path=_FIXTURES / "small_2pl_bank.json",
    ),
    "demo_mixed": PoolEntry(
        pool_id="demo_mixed",
        title="Mixed 2PL/3PL demo bank",
        description=(
            "252 simulated items across 3 domains with a 2PL/3PL mix, wide "
            "symmetric difficulty, and multi-item enemy sets — exercises every "
            "linear use case (multi-domain balance, guessing, parallel forms + "
            "exposure, extreme cut scores)."
        ),
        path=_FIXTURES / "demo_bank.json",
    ),
}


#: Imported item banks (backlog #9): each ``app/data/item_banks/<bank_id>/pool.json``
#: is an administrable derivation written by ``services/item_bank.ingest_export`` in
#: the standard pool-document format. Scanned per call (no cache): imports become
#: visible immediately in every process sharing the volume (API + worker).
IMPORTED_BANKS_DIR = Path(__file__).parent.parent / "data" / "item_banks"


def _imported_entries() -> dict[str, PoolEntry]:
    out: dict[str, PoolEntry] = {}
    if not IMPORTED_BANKS_DIR.is_dir():
        return out
    for bank_dir in sorted(p for p in IMPORTED_BANKS_DIR.iterdir() if p.is_dir()):
        pool_path = bank_dir / "pool.json"
        if pool_path.is_file() and bank_dir.name not in _CATALOG:
            out[bank_dir.name] = PoolEntry(
                pool_id=bank_dir.name,
                title=f"Imported bank: {bank_dir.name}",
                description=(
                    "administrable items from an imported item-factory bank "
                    "(see GET /item-bank for the full two-axis record)"
                ),
                path=pool_path,
            )
        field_path = bank_dir / "field_pool.json"
        field_id = f"{bank_dir.name}-field"
        if field_path.is_file() and field_id not in _CATALOG:
            out[field_id] = PoolEntry(
                pool_id=field_id,
                title=f"Field-study pool: {bank_dir.name}",
                description=(
                    "field-eligible items (editorial live/pilot) from an imported "
                    "bank — CONTENT-ONLY: no parameters; assembles feasibility-only "
                    "forms for calibration field studies"
                ),
                path=field_path,
                kind="field",
            )
    return out


def resolve(pool_id: str) -> PoolEntry:
    entry = _CATALOG.get(pool_id) or _imported_entries().get(pool_id)
    if entry is None:
        raise KeyError(f"unknown pool_id {pool_id!r}")
    return entry


def is_known(pool_id: str) -> bool:
    return pool_id in _CATALOG or pool_id in _imported_entries()


def is_field_pool(pool_id: str) -> bool:
    try:
        return resolve(pool_id).kind == "field"
    except KeyError:
        return False


def load_pool_by_id(pool_id: str = DEFAULT_POOL_ID) -> ItemPool:
    entry = resolve(pool_id)
    if entry.kind == "field":
        raise ValueError(
            f"pool {pool_id!r} is a content-only field-study pool — it has no "
            "parameters; use load_assembly_pool for assembly or GET /item-bank "
            "for the record"
        )
    return load_pool(entry.path)


def load_assembly_pool(pool_id: str = DEFAULT_POOL_ID) -> ItemPool | FieldPool:
    """The assembly-path resolver: parametric pools load as :class:`ItemPool`,
    field-study pools as :class:`FieldPool` (content-only assembly)."""
    entry = resolve(pool_id)
    if entry.kind == "field":
        return load_field_pool(entry.path)
    return load_pool(entry.path)


def load_document_by_id(pool_id: str = DEFAULT_POOL_ID) -> dict:
    return load_bank_document(resolve(pool_id).path)


def catalog() -> list[PoolEntry]:
    return [*_CATALOG.values(), *_imported_entries().values()]
