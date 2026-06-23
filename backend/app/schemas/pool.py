"""Read-only schema for the **simulated** item bank (plan §8 — item bank is input).

Surfacing the bank lets the UI demonstrate end-to-end workflows with genuine
simulated data when no real item-factory export is wired. The ``simulated`` flag +
``provenance`` make the synthetic origin explicit; ``stem``/``options``/
``answer_key`` are synthetic display content (scoring is driven by the 2PL model on
the canonical metric, not the literal key).
"""

from __future__ import annotations

from pydantic import BaseModel


class PoolItemOption(BaseModel):
    key: str
    text: str


class PoolItem(BaseModel):
    item_id: str
    a: float
    b: float
    c: float = 0.0
    scaling_d: float
    tags: dict[str, str] = {}
    enemy_of: list[str] = []
    # Synthetic, display-only demonstration content.
    stem: str | None = None
    options: list[PoolItemOption] = []
    answer_key: str | None = None


class PoolDocument(BaseModel):
    pool_id: str
    simulated: bool
    provenance: str | None = None
    model: str
    scaling_d: float
    n_items: int
    # counts per tag dimension -> value -> count (drives feasibility hints in the UI)
    tag_summary: dict[str, dict[str, int]]
    items: list[PoolItem]


class PoolSummary(BaseModel):
    """One entry in the pool catalog (no item payload) — for the pool selector."""

    pool_id: str
    title: str
    description: str
    model: str
    simulated: bool
    n_items: int
    n_3pl: int
    domains: list[str]


class PoolCatalog(BaseModel):
    default_pool_id: str
    pools: list[PoolSummary]
