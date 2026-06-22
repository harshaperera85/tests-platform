"""Calibrated item pool loading.

The item-factory export contract is **not wired yet** (plan §8, "[pin against
repo]"). Until it is, assembly and scoring read a small fixture pool that mirrors
the CAT prototype's ``small_2pl_bank.json`` shape. Swapping in the real export is
later a matter of pointing :func:`load_pool` at the export adapter — the rest of
the codebase only sees :class:`ItemPool`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

from app.psychometrics.params import ItemParameters, normalize_to_canonical

_FIXTURE_DIR = Path(__file__).parent / "fixtures"
DEFAULT_BANK = _FIXTURE_DIR / "small_2pl_bank.json"


class ItemPool:
    """An ordered, immutable collection of canonical-metric items."""

    def __init__(self, items: Sequence[ItemParameters]) -> None:
        self._items: tuple[ItemParameters, ...] = tuple(
            normalize_to_canonical(it) for it in items
        )
        self._by_id: dict[str, ItemParameters] = {it.item_id: it for it in self._items}
        if len(self._by_id) != len(self._items):
            raise ValueError("duplicate item_id in pool")

    @property
    def items(self) -> tuple[ItemParameters, ...]:
        return self._items

    def get(self, item_id: str) -> ItemParameters:
        return self._by_id[item_id]

    def subset(self, item_ids: Sequence[str]) -> list[ItemParameters]:
        """Items for ``item_ids``, preserving the requested order."""
        return [self._by_id[i] for i in item_ids]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[ItemParameters]:
        return iter(self._items)


def load_pool(path: Path | str = DEFAULT_BANK) -> ItemPool:
    """Load a pool from a bank JSON file (fixture shape)."""
    data = json.loads(Path(path).read_text())
    src_d = float(
        data.get("metric", {}).get(
            "scaling_d", ItemParameters.model_fields["scaling_d"].default
        )
    )
    items: list[ItemParameters] = []
    for raw in data["items"]:
        items.append(
            ItemParameters(
                item_id=raw["item_id"],
                a=raw["a"],
                b=raw["b"],
                c=raw.get("c", 0.0),
                scaling_d=raw.get("scaling_d", src_d),
                tags=raw.get("tags", {}),
                enemy_of=raw.get("enemy_of", ()),
            )
        )
    return ItemPool(items)


def load_default_pool() -> ItemPool:
    """The fixture pool used everywhere until the item-factory export is pinned."""
    return load_pool(DEFAULT_BANK)
