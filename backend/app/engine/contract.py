"""The administration-model contract.

Every administration model (linear, cat, loft, mst, ...) implements the single
``AdministrationStrategy`` interface. The engine core drives a session purely
through these types and never branches on model type — that is the structural
extensibility guarantee (CLAUDE.md golden rule 1).

Phase 0 ships only the contract and supporting types. No concrete strategy lives
here; strategies go in ``engine/strategies/`` and self-register via ``registry``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Navigation(BaseModel):
    """Navigation capabilities exposed to the test-taker / Sessions module."""

    can_review: bool = False
    can_skip: bool = False
    can_navigate_back: bool = False
    fixed_length: bool = True
    total_items: int | None = None  # None when adaptive / unknown ahead of time


class NextAction(BaseModel):
    """What the engine should do next: present item(s)/module, or complete."""

    kind: Literal["present", "complete"]
    payload: dict[str, Any] = Field(default_factory=dict)
    navigation: Navigation


class TerminationDecision(BaseModel):
    """Whether the session is complete and why."""

    complete: bool
    reason: str | None = None  # max_items, min_sem, sprt, end_of_form, ...


class SessionState(BaseModel):
    """Opaque-to-the-core administration state for one in-flight session.

    The engine core treats this as a black box and only passes it back to the
    owning strategy. Concrete strategies refine ``data`` with their own typed
    payloads in Phase 1+.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_type: str
    session_id: str
    position: int = 0
    completed: bool = False
    data: dict[str, Any] = Field(default_factory=dict)


class ScoreResult(BaseModel):
    """Result of scoring a session on the canonical theta metric.

    All theta values are normalized through ``psychometrics/`` (the single source
    of truth = the mirt scoring service). Mind the D-scaling mismatch.
    """

    theta: float | None = None
    standard_error: float | None = None
    scale: str = "canonical"
    detail: dict[str, Any] = Field(default_factory=dict)


class AdministrationStrategy(ABC):
    """One per administration model. Pure-ish: state in, state/action out.

    Subclasses set the two class attributes below and implement the six methods.
    They are wired into the engine by decorating with ``registry.register``.
    """

    #: stable identifier, e.g. "linear", "cat", "loft", "mst"
    model_type: str
    #: the per-model config branch (a Pydantic model from ``schemas.test_config``)
    config_schema: type[BaseModel]

    @abstractmethod
    def initialize(
        self, config: BaseModel, pool_ref: Any, context: dict[str, Any]
    ) -> SessionState:
        """Start a session.

        Linear/LOFT/MST: assemble or load the form/panel here.
        CAT: initialize theta and pick the first item (neural cold-start).
        """

    @abstractmethod
    def next_action(self, state: SessionState) -> NextAction:
        """Return the next thing to present, or signal completion."""

    @abstractmethod
    def record_response(self, state: SessionState, response: Any) -> SessionState:
        """Fold a response into state. CAT: update theta. Linear: advance."""

    @abstractmethod
    def is_complete(self, state: SessionState) -> TerminationDecision:
        """Decide whether the session has terminated, and why."""

    @abstractmethod
    def score(self, state: SessionState) -> ScoreResult:
        """Score via the canonical metric (delegates to ``psychometrics/``)."""

    @abstractmethod
    def capabilities(self) -> Navigation:
        """Navigation capabilities for this model (drives the UI/Sessions)."""
