"""Delivery-time helpers shared by fixed-order strategies (G5).

Support module, not a strategy: seeded item-order randomization (Luecht &
Sireci security method (i)) and embedded-pretest interleaving (the ATS
``PRE>`` design). All derivations are keyed by ``(seed, item_id)`` — order-
independent (lane convention C5), so the same session seed always yields the
same delivery order regardless of construction order.
"""

from __future__ import annotations

import zlib

from app.psychometrics import pools
from app.schemas.test_config import DeliveryOptions


def _key(seed: int, tag: str, item_id: str) -> int:
    return zlib.crc32(f"{seed}:{tag}:{item_id}".encode())


def session_seed(context: dict, session_id: str) -> int:
    """Explicit ``context['seed']``, else a stable hash of the session id."""
    seed = context.get("seed")
    if seed is not None:
        return int(seed)
    return sum((i + 1) * b for i, b in enumerate(session_id.encode())) or 1


def draw_pretest_items(
    pool_id: str, n_items: int, seed: int, exclude: set[str]
) -> list[str]:
    """Seeded draw of ``n_items`` pretest ids from ``pool_id`` (field or
    calibrated pool), excluding operational items. Fails loudly on shortfall."""
    if not pools.is_known(pool_id):
        raise ValueError(f"pretest pool {pool_id!r} is unknown")
    pool = pools.load_assembly_pool(pool_id)
    candidates = [it.item_id for it in pool.items if it.item_id not in exclude]
    if len(candidates) < n_items:
        raise ValueError(
            f"pretest pool {pool_id!r} has only {len(candidates)} eligible "
            f"item(s) for n_items={n_items}"
        )
    ranked = sorted(candidates, key=lambda iid: _key(seed, "pre", iid))
    return ranked[:n_items]


def delivery_order(
    operational: list[str],
    pretest: list[str],
    seed: int,
    randomize: bool,
) -> list[str]:
    """The per-session presentation order.

    - ``randomize``: one keyed sort over the merged set — operational and
      pretest items are indistinguishable by position.
    - fixed order: operational order is preserved; each pretest item lands at
      a seeded position (so pilots are not always trailing).
    """
    if randomize:
        return sorted(operational + pretest, key=lambda iid: _key(seed, "ord", iid))
    order = list(operational)
    for iid in sorted(pretest, key=lambda p: _key(seed, "pos", p)):
        order.insert(_key(seed, "pos", iid) % (len(order) + 1), iid)
    return order


def apply_delivery(
    operational: list[str],
    delivery: DeliveryOptions,
    seed: int,
) -> tuple[list[str], list[str]]:
    """Resolve (presentation_order, pretest_item_ids) for one session."""
    pretest_ids: list[str] = []
    if delivery.pretest is not None:
        pretest_ids = draw_pretest_items(
            delivery.pretest.pool_id,
            delivery.pretest.n_items,
            seed,
            exclude=set(operational),
        )
    if not pretest_ids and not delivery.randomize_item_order:
        return list(operational), []
    return (
        delivery_order(
            operational, pretest_ids, seed, delivery.randomize_item_order
        ),
        pretest_ids,
    )
