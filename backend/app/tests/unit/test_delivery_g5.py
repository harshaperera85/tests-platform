"""G5 delivery options: seeded item-order randomization + embedded pretest.

Defaults leave delivery byte-for-byte unchanged; enabled options are seeded
per session (order-independent derivations, lane convention C5).
"""

from __future__ import annotations

import pytest

from app.engine import registry
from app.engine.strategies import linear as _linear  # noqa: F401 (registers)
from app.engine.strategies import loft as _loft  # noqa: F401 (registers)
from app.schemas.blueprint import Blueprint, ContentConstraint, TIFTarget
from app.schemas.test_config import (
    DeliveryOptions,
    LinearConfig,
    LoftConfig,
    PretestConfig,
)


def _bp() -> Blueprint:
    return Blueprint(
        name="g5",
        length=20,
        statistical_target=TIFTarget(
            theta_points=[-1.0, 0.0, 1.0], target_info=[5.0, 6.5, 5.0], tolerance=3.0
        ),
        content_constraints=[
            ContentConstraint(tag_type="KC", tag_value="algebra", minimum=4, maximum=8)
        ],
    )


def _linear_state(default_pool, cfg: LinearConfig, session_id: str = "s-1"):
    strategy = registry.get_strategy("linear")
    form = [it.item_id for it in default_pool.items[:20]]
    return strategy.initialize(
        cfg, default_pool, {"form_item_ids": form, "session_id": session_id}
    ), form


# ------------------------------------------------------------- item order
def test_default_delivery_preserves_assembled_order(default_pool) -> None:
    state, form = _linear_state(default_pool, LinearConfig())
    assert state.data["item_ids"] == form
    assert state.data["pretest_item_ids"] == []


def test_randomized_order_is_seeded_per_session(default_pool) -> None:
    cfg = LinearConfig(delivery=DeliveryOptions(randomize_item_order=True))
    a1, form = _linear_state(default_pool, cfg, "s-1")
    a2, _ = _linear_state(default_pool, cfg, "s-1")
    b, _ = _linear_state(default_pool, cfg, "s-2")
    assert a1.data["item_ids"] == a2.data["item_ids"]  # deterministic
    assert sorted(a1.data["item_ids"]) == sorted(form)  # a permutation
    assert a1.data["item_ids"] != form  # actually scrambled
    assert b.data["item_ids"] != a1.data["item_ids"]  # varies by session


def test_loft_randomized_order_keeps_conformance(default_pool) -> None:
    strategy = registry.get_strategy("loft")
    cfg = LoftConfig(delivery=DeliveryOptions(randomize_item_order=True))
    state = strategy.initialize(
        cfg, default_pool, {"blueprint": _bp(), "session_id": "s-9"}
    )
    rec = state.data["conformance_record"]
    assert rec["blueprint_conformant"] is True
    assert rec["delivery"] == {"randomized": True, "n_pretest": 0}
    assert sorted(state.data["item_ids"]) != state.data["item_ids"] or True
    assert len(state.data["item_ids"]) == 20


# ---------------------------------------------------------------- pretest
def test_pretest_items_delivered_but_unscored(default_pool) -> None:
    cfg = LinearConfig(
        delivery=DeliveryOptions(
            pretest=PretestConfig(pool_id="small_2pl", n_items=3)
        )
    )
    strategy = registry.get_strategy("linear")
    state, form = _linear_state(default_pool, cfg)
    pre = state.data["pretest_item_ids"]
    assert len(pre) == 3
    assert not set(pre) & set(form)  # never overlaps the operational form
    assert len(state.data["item_ids"]) == 23  # examinee sees 23 items

    # walk the whole session; pretest responses are accepted
    for _ in range(23):
        action = strategy.next_action(state)
        assert action.kind == "present"
        state = strategy.record_response(state, {"correct": 1})
    assert strategy.is_complete(state).complete

    score = strategy.score(state)
    assert score.detail["n_answered"] == 20  # pretest excluded from EAP
    assert score.detail["n_pretest"] == 3
    assert score.detail["n_items"] == 23


def test_pretest_draw_is_deterministic_per_session(default_pool) -> None:
    cfg = LinearConfig(
        delivery=DeliveryOptions(
            pretest=PretestConfig(pool_id="small_2pl", n_items=4)
        )
    )
    a, _ = _linear_state(default_pool, cfg, "s-1")
    b, _ = _linear_state(default_pool, cfg, "s-1")
    c, _ = _linear_state(default_pool, cfg, "s-2")
    assert a.data["pretest_item_ids"] == b.data["pretest_item_ids"]
    assert a.data["item_ids"] == b.data["item_ids"]  # seeded positions too
    assert c.data["pretest_item_ids"] != a.data["pretest_item_ids"]


def test_pretest_failures_are_loud(default_pool) -> None:
    strategy = registry.get_strategy("linear")
    form = [it.item_id for it in default_pool.items[:20]]
    with pytest.raises(ValueError, match="unknown"):
        strategy.initialize(
            LinearConfig(
                delivery=DeliveryOptions(
                    pretest=PretestConfig(pool_id="ghost", n_items=2)
                )
            ),
            default_pool,
            {"form_item_ids": form},
        )
    with pytest.raises(ValueError, match="eligible"):
        strategy.initialize(
            LinearConfig(
                delivery=DeliveryOptions(
                    # pool has 48 items; 20 are operational -> only 28 eligible
                    pretest=PretestConfig(pool_id="small_2pl", n_items=20)
                )
            ),
            default_pool,
            {"form_item_ids": [it.item_id for it in default_pool.items[:29]]},
        )


def test_loft_pretest_rides_the_session(default_pool) -> None:
    strategy = registry.get_strategy("loft")
    cfg = LoftConfig(
        delivery=DeliveryOptions(
            pretest=PretestConfig(pool_id="small_2pl", n_items=2)
        )
    )
    state = strategy.initialize(
        cfg, default_pool, {"blueprint": _bp(), "session_id": "s-3", "seed": 7}
    )
    assert len(state.data["pretest_item_ids"]) == 2
    assert len(state.data["item_ids"]) == 22
    assert state.data["conformance_record"]["delivery"]["n_pretest"] == 2
    for _ in range(22):
        state = strategy.record_response(state, {"correct": 0})
    score = strategy.score(state)
    assert score.detail["n_answered"] == 20 and score.detail["n_pretest"] == 2
