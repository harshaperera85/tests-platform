"""Proves the strategy registry: register, look up, isolation guarantees.

This is the structural guarantee behind CLAUDE.md golden rule 1 — a model plugs in
via ``@register`` and resolves by ``model_type`` with no core edits.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.engine import registry
from app.engine.contract import (
    AdministrationStrategy,
    Navigation,
    NextAction,
    ScoreResult,
    SessionState,
    TerminationDecision,
)


class _DummyConfig(BaseModel):
    administration_model: str = "dummy"


class _DummyStrategy(AdministrationStrategy):
    model_type = "dummy"
    config_schema = _DummyConfig

    def initialize(self, config, pool_ref, context) -> SessionState:  # noqa: ANN001
        return SessionState(model_type=self.model_type, session_id="s")

    def next_action(self, state: SessionState) -> NextAction:
        return NextAction(kind="complete", navigation=self.capabilities())

    def record_response(self, state: SessionState, response) -> SessionState:  # noqa: ANN001
        return state

    def is_complete(self, state: SessionState) -> TerminationDecision:
        return TerminationDecision(complete=True, reason="end_of_form")

    def score(self, state: SessionState) -> ScoreResult:
        return ScoreResult(theta=0.0)

    def capabilities(self) -> Navigation:
        return Navigation(fixed_length=True, total_items=1)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot/restore the global registry so tests don't leak state."""
    saved = dict(registry._REGISTRY)
    registry._REGISTRY.clear()
    yield
    registry._REGISTRY.clear()
    registry._REGISTRY.update(saved)


def test_register_then_lookup_returns_instance() -> None:
    registry.register(_DummyStrategy)
    assert registry.is_registered("dummy")
    strategy = registry.get_strategy("dummy")
    assert isinstance(strategy, _DummyStrategy)
    assert strategy.model_type == "dummy"


def test_registered_models_lists_model_type() -> None:
    registry.register(_DummyStrategy)
    assert registry.registered_models() == ["dummy"]


def test_unknown_model_type_raises() -> None:
    with pytest.raises(KeyError):
        registry.get_strategy("does-not-exist")


def test_duplicate_registration_raises() -> None:
    registry.register(_DummyStrategy)
    with pytest.raises(ValueError):
        registry.register(_DummyStrategy)


def test_empty_model_type_rejected() -> None:
    class _Bad(_DummyStrategy):
        model_type = ""

    with pytest.raises(ValueError):
        registry.register(_Bad)
