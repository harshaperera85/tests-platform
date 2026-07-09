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
    # canonical slope-intercept (logistic D=1); None on content-only FIELD pools
    # (uncalibrated items — parameters honestly absent, never fabricated)
    a: float | None = None
    d: float | None = None
    c: float = 0.0
    u: float = 1.0
    # difficulty view (b = -d/a) — surfaced for display; None when uncalibrated
    b: float | None = None
    scaling_d: float | None = None
    #: True on field-study items that do carry parameters in their bank (anchors)
    calibrated_anchor: bool | None = None
    tags: dict[str, str] = {}
    enemy_of: list[str] = []
    # calibration uncertainty (calibrated pools only; None for synthetic)
    se_a: float | None = None
    se_d: float | None = None
    se_b: float | None = None
    # Synthetic, display-only demonstration content.
    stem: str | None = None
    options: list[PoolItemOption] = []
    answer_key: str | None = None


class PoolDocument(BaseModel):
    pool_id: str
    simulated: bool
    provenance: str | None = None
    model: str
    # metric contract (axis 1 scaling, axis 2 form, synthetic vs calibrated);
    # scaling_d is None on content-only FIELD pools (no parameters, no metric)
    scaling_d: float | None = None
    form: str
    kind: str
    n_items: int
    #: "parametric" or "field" (content-only field-study pool)
    pool_kind: str = "parametric"
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


class ItemExposure(BaseModel):
    """Cumulative longitudinal usage of one item across assemblies over time."""

    item_id: str
    published: int = 0  # real exposure (forms that reached published)
    assembled: int = 0  # draft assembly usage (tracked separately)
    total: int = 0
    n_forms: int = 0
    last_used: str | None = None


class PoolExposure(BaseModel):
    pool_id: str
    #: which contexts count as "real" exposure (default: published)
    exposure_contexts: list[str]
    items: list[ItemExposure]
