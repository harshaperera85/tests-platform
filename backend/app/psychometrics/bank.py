"""Calibrated item pool loading.

The item-factory export contract is **not wired yet** (plan §8, "[pin against
repo]"). Until it is, assembly and scoring read fixture pools that declare their
metric explicitly. Swapping in the real export is later a matter of pointing
:func:`load_pool` at the export adapter — the rest of the codebase only sees
:class:`ItemPool` on the canonical metric.

Every pool MUST declare ``metric = {scaling_d, form, kind}`` (the metric contract,
:func:`app.psychometrics.params.require_metric`). Loading converts to the canonical
slope-intercept D=1 metric at ingest and refuses undeclared metrics.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

from app.psychometrics.params import (
    B_CONSISTENCY_TOL,
    ItemParameters,
    PoolMetric,
    normalize_to_canonical,
    require_metric,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures"
DEFAULT_BANK = _FIXTURE_DIR / "small_2pl_bank.json"


class ItemPool:
    """An ordered, immutable collection of canonical-metric items."""

    def __init__(
        self, items: Sequence[ItemParameters], metric: PoolMetric | None = None
    ) -> None:
        self._items: tuple[ItemParameters, ...] = tuple(
            normalize_to_canonical(it) for it in items
        )
        self._by_id: dict[str, ItemParameters] = {it.item_id: it for it in self._items}
        if len(self._by_id) != len(self._items):
            raise ValueError("duplicate item_id in pool")
        self.metric = metric

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


def _item_from_raw(raw: dict, metric: PoolMetric, where: str) -> ItemParameters:
    """Build a canonical-form item from a raw record under the declared metric."""
    c = float(raw.get("c", 0.0))
    u = float(raw.get("u", 1.0))
    if metric.form == "slope_intercept":
        a = float(raw["a"])
        d = float(raw["d"])
        # On-load consistency: a declared b must agree with -d/a.
        if "b" in raw and abs(float(raw["b"]) - (-d / a)) > B_CONSISTENCY_TOL:
            raise ValueError(
                f"{where}: item {raw['item_id']} declares b={raw['b']} but "
                f"-d/a={-d / a:.6f} (slope-intercept inconsistency)."
            )
    else:  # traditional (a, b) -> slope-intercept
        a = float(raw["a"])
        d = -a * float(raw["b"])
    se_fields: dict[str, float | None] = {}
    if metric.kind == "calibrated":
        se_fields = {
            "se_a": raw.get("se_a"),
            "se_d": raw.get("se_d"),
            "cov_ad": raw.get("cov_ad"),
            "se_b": raw.get("se_b"),
        }
    return ItemParameters(
        item_id=raw["item_id"],
        a=a,
        d=d,
        c=c,
        u=u,
        scaling_d=metric.scaling_d,
        tags=raw.get("tags", {}),
        enemy_of=raw.get("enemy_of", ()),
        **se_fields,
    )


def load_bank_document(path: Path | str = DEFAULT_BANK) -> dict:
    """Return the raw bank JSON, including simulated demo content + provenance."""
    return json.loads(Path(path).read_text())


def load_pool(path: Path | str = DEFAULT_BANK) -> ItemPool:
    """Load a pool from a bank JSON file, enforcing the metric contract."""
    where = str(path)
    data = json.loads(Path(path).read_text())
    metric = require_metric(data.get("metric"), where=where)
    items = [_item_from_raw(raw, metric, where) for raw in data["items"]]
    return ItemPool(items, metric=metric)


def load_default_pool() -> ItemPool:
    """The fixture pool used everywhere until the item-factory export is pinned."""
    return load_pool(DEFAULT_BANK)
