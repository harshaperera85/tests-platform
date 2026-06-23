"""Read-only access to the **simulated** item bank (plan §8).

Additive surface so the UI can demonstrate the linear workflow end-to-end with
genuine simulated data (item metadata, tag availability, content) when no real
item-factory export is wired. Reads the fixture document; changes nothing.
"""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter

from app.psychometrics.bank import load_bank_document
from app.schemas.pool import PoolDocument, PoolItem

router = APIRouter(prefix="/pool", tags=["pool"])

_TAG_DIMENSIONS = ("KC", "Bloom", "TIMSS", "domain")


@router.get("/items", response_model=PoolDocument)
def get_pool_items() -> PoolDocument:
    """Return the simulated item bank with params, tags, and synthetic content."""
    doc = load_bank_document()
    raw_items = doc["items"]
    metric = doc.get("metric", {})
    scaling_d = float(metric.get("scaling_d", 1.702))

    items = [
        PoolItem(
            item_id=it["item_id"],
            a=it["a"],
            b=it["b"],
            c=it.get("c", 0.0),
            scaling_d=it.get("scaling_d", scaling_d),
            tags=it.get("tags", {}),
            enemy_of=it.get("enemy_of", []),
            stem=it.get("stem"),
            options=it.get("options", []),
            answer_key=it.get("answer_key"),
        )
        for it in raw_items
    ]

    tag_summary: dict[str, dict[str, int]] = {}
    for dim in _TAG_DIMENSIONS:
        counts = Counter(
            it["tags"][dim] for it in raw_items if dim in it.get("tags", {})
        )
        if counts:
            tag_summary[dim] = dict(sorted(counts.items()))

    return PoolDocument(
        simulated=bool(doc.get("simulated", False)),
        provenance=doc.get("provenance"),
        model=metric.get("model", "2PL"),
        scaling_d=scaling_d,
        n_items=len(items),
        tag_summary=tag_summary,
        items=items,
    )
