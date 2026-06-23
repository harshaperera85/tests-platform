"""Read-only access to the **simulated** item banks (plan §8).

Additive surface so the UI can demonstrate the linear workflow end-to-end with
genuine simulated data when no real item-factory export is wired. Lists the pool
catalog and serves a selected bank by ``pool_id``. Reads fixtures; changes nothing.
"""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Query

from app.psychometrics import pools
from app.schemas.pool import PoolCatalog, PoolDocument, PoolItem, PoolSummary

router = APIRouter(prefix="/pool", tags=["pool"])

_TAG_DIMENSIONS = ("KC", "Bloom", "TIMSS", "domain")


@router.get("/catalog", response_model=PoolCatalog)
def get_pool_catalog() -> PoolCatalog:
    """List the selectable simulated banks (for the pool selector)."""
    summaries: list[PoolSummary] = []
    for entry in pools.catalog():
        doc = pools.load_document_by_id(entry.pool_id)
        raw = doc["items"]
        domains = sorted(
            {it["tags"]["domain"] for it in raw if "domain" in it.get("tags", {})}
        )
        summaries.append(
            PoolSummary(
                pool_id=entry.pool_id,
                title=entry.title,
                description=entry.description,
                model=doc.get("metric", {}).get("model", "2PL"),
                simulated=bool(doc.get("simulated", False)),
                n_items=len(raw),
                n_3pl=sum(1 for it in raw if it.get("c", 0.0) > 0),
                domains=domains,
            )
        )
    return PoolCatalog(default_pool_id=pools.DEFAULT_POOL_ID, pools=summaries)


@router.get("/items", response_model=PoolDocument)
def get_pool_items(
    pool_id: str = Query(default=pools.DEFAULT_POOL_ID),
) -> PoolDocument:
    """Return a simulated bank with params, tags, and synthetic content."""
    if not pools.is_known(pool_id):
        raise HTTPException(status_code=404, detail=f"unknown pool_id {pool_id!r}")
    doc = pools.load_document_by_id(pool_id)
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
        pool_id=pool_id,
        simulated=bool(doc.get("simulated", False)),
        provenance=doc.get("provenance"),
        model=metric.get("model", "2PL"),
        scaling_d=scaling_d,
        n_items=len(items),
        tag_summary=tag_summary,
        items=items,
    )
