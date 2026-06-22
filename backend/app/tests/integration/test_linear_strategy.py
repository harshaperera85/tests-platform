"""Integration: LinearStrategy through the full administration contract."""

from __future__ import annotations

import pytest

import app.engine.strategies  # noqa: F401  (registers LinearStrategy)
from app.engine import registry
from app.psychometrics.information import prob_correct
from app.schemas.test_config import LinearConfig, LinearNavigationConfig


def _simulate(strategy, state, pool, true_theta):
    """Walk a deterministic examinee through the form to completion."""
    steps = 0
    while not strategy.is_complete(state).complete:
        action = strategy.next_action(state)
        assert action.kind == "present"
        item_id = action.payload["item_id"]
        u = 1 if prob_correct(pool.get(item_id), true_theta) >= 0.5 else 0
        state = strategy.record_response(state, {"item_id": item_id, "correct": u})
        steps += 1
    return state, steps


def test_linear_is_registered() -> None:
    assert registry.is_registered("linear")
    assert isinstance(registry.get_strategy("linear").config_schema, type)


def test_assemble_initialize_step_score(default_pool, linear_blueprint) -> None:
    strategy = registry.get_strategy("linear")
    state = strategy.initialize(
        LinearConfig(),
        default_pool,
        {"blueprint": linear_blueprint, "session_id": "s1"},
    )
    assert len(state.data["item_ids"]) == linear_blueprint.length
    assert strategy.capabilities(state).total_items == linear_blueprint.length

    state, steps = _simulate(strategy, state, default_pool, true_theta=0.8)
    assert steps == linear_blueprint.length
    assert strategy.is_complete(state).reason == "end_of_form"
    assert strategy.next_action(state).kind == "complete"

    result = strategy.score(state)
    assert result.scale == "canonical"
    assert result.detail["n_answered"] == linear_blueprint.length
    # EAP should land near the true theta for a 20-item form.
    assert result.theta == pytest.approx(0.8, abs=0.5)
    assert result.standard_error < 1.0


def test_preassembled_form_path(default_pool) -> None:
    strategy = registry.get_strategy("linear")
    item_ids = [it.item_id for it in default_pool.items[:6]]
    state = strategy.initialize(
        LinearConfig(form_ref="form-123"),
        default_pool,
        {"form_item_ids": item_ids},
    )
    assert state.data["item_ids"] == item_ids
    state, steps = _simulate(strategy, state, default_pool, true_theta=-0.5)
    assert steps == 6
    assert strategy.score(state).detail["n_answered"] == 6


def test_navigation_config_flows_through(default_pool) -> None:
    strategy = registry.get_strategy("linear")
    cfg = LinearConfig(
        navigation=LinearNavigationConfig(can_skip=True, can_review=False)
    )
    state = strategy.initialize(cfg, default_pool, {"form_item_ids": ["I001", "I003"]})
    nav = strategy.capabilities(state)
    assert nav.can_skip is True
    assert nav.can_review is False
    assert nav.fixed_length is True


def test_initialize_without_form_source_raises(default_pool) -> None:
    strategy = registry.get_strategy("linear")
    with pytest.raises(ValueError):
        strategy.initialize(LinearConfig(), default_pool, {})
