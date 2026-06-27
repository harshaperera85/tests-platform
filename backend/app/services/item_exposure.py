"""Longitudinal item-exposure history: record cumulative usage + query it.

Persists per-item usage *across* assembly/administration events (append-only
``item_usage_event``) and exposes cumulative counts. This is the longitudinal
complement to the within-batch exposure controls (overlap / max-use / rate, which
govern one assembly) and is distinct from CAT administration-time exposure
(Sympson-Hetter etc.). The cumulative counts can optionally feed back into assembly
eligibility (see the compiler / ExposureFeedback) — opt-in, default-off.

"What counts as exposure" is explicit and configurable: by default only
``published`` forms count; ``assembled`` (draft) usage is tracked separately.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.form import FormRow
from app.models.item_usage_event import ItemUsageEventRow

#: Contexts that count as real exposure by default.
DEFAULT_EXPOSURE_CONTEXTS: tuple[str, ...] = ("published",)


def record_form_usage(db: Session, form: FormRow, context: str) -> int:
    """Append one usage event per item in ``form`` under ``context``. Returns count."""
    for item_id in form.item_ids:
        db.add(
            ItemUsageEventRow(
                item_id=item_id,
                form_id=form.id,
                test_id=form.test_id,
                pool_id=form.pool_id,
                context=context,
            )
        )
    db.commit()
    return len(form.item_ids)


def exposure_counts(
    db: Session,
    *,
    contexts: Sequence[str] = DEFAULT_EXPOSURE_CONTEXTS,
    pool_id: str | None = None,
) -> dict[str, int]:
    """Cumulative usage count per item_id over the given ``contexts``."""
    q = (
        select(ItemUsageEventRow.item_id, func.count())
        .where(ItemUsageEventRow.context.in_(list(contexts)))
        .group_by(ItemUsageEventRow.item_id)
    )
    if pool_id is not None:
        q = q.where(ItemUsageEventRow.pool_id == pool_id)
    return {item_id: int(n) for item_id, n in db.execute(q).all()}


def exposure_summary(db: Session, *, pool_id: str) -> dict[str, dict]:
    """Per-item exposure detail for a pool: published/assembled counts, last used.

    Returns ``{item_id: {published, assembled, total, last_used, n_forms}}``.
    """
    rows = db.execute(
        select(
            ItemUsageEventRow.item_id,
            ItemUsageEventRow.context,
            func.count(),
            func.max(ItemUsageEventRow.created_at),
            func.count(func.distinct(ItemUsageEventRow.form_id)),
        )
        .where(ItemUsageEventRow.pool_id == pool_id)
        .group_by(ItemUsageEventRow.item_id, ItemUsageEventRow.context)
    ).all()
    out: dict[str, dict] = {}
    for item_id, context, n, last_used, n_forms in rows:
        e = out.setdefault(
            item_id,
            {
                "published": 0,
                "assembled": 0,
                "total": 0,
                "last_used": None,
                "n_forms": 0,
            },
        )
        e[context] = int(n)
        e["total"] += int(n)
        e["n_forms"] += int(n_forms)
        prev = e["last_used"]
        if last_used is not None and (prev is None or last_used > prev):
            e["last_used"] = last_used
    return out
