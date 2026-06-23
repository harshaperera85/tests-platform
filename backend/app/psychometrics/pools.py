"""Catalog of selectable item pools (the plan's ``item_pool_ref``, §8).

Until the item-factory export is wired, the platform ships **simulated** banks so
every workflow is demonstrable end-to-end. Each pool is a calibrated bank file;
callers select one by ``pool_id``. The default stays the small smoke bank so
existing behavior/tests are unchanged; the UI defaults to the richer demo bank.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.psychometrics.bank import ItemPool, load_bank_document, load_pool

_FIXTURES = Path(__file__).parent / "fixtures"

#: Default pool — the small 2PL smoke bank (stable for tests / existing callers).
DEFAULT_POOL_ID = "small_2pl"


@dataclass(frozen=True)
class PoolEntry:
    pool_id: str
    title: str
    description: str
    path: Path


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


def resolve(pool_id: str) -> PoolEntry:
    try:
        return _CATALOG[pool_id]
    except KeyError as exc:
        raise KeyError(f"unknown pool_id {pool_id!r}") from exc


def is_known(pool_id: str) -> bool:
    return pool_id in _CATALOG


def load_pool_by_id(pool_id: str = DEFAULT_POOL_ID) -> ItemPool:
    return load_pool(resolve(pool_id).path)


def load_document_by_id(pool_id: str = DEFAULT_POOL_ID) -> dict:
    return load_bank_document(resolve(pool_id).path)


def catalog() -> list[PoolEntry]:
    return list(_CATALOG.values())
