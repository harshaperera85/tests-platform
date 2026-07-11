"""The ``TestConfig`` discriminated union, keyed by ``administration_model``.

A new administration model adds a branch here and a strategy file — nothing else
in the engine changes (plan §5, §15). Phase 0 ships minimal placeholder branches
for ``linear`` and ``cat``; fields fill out in Phase 1/2.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class LinearNavigationConfig(BaseModel):
    """How a test-taker may move through a linear form."""

    can_review: bool = True
    can_skip: bool = False
    can_navigate_back: bool = True


class LinearScoringConfig(BaseModel):
    """How a completed linear form is scored on the canonical theta metric."""

    method: Literal["eap"] = "eap"


class LinearConfig(BaseModel):
    """Linear fixed-form configuration (Phase 1).

    Either ``form_ref`` (a pre-assembled form) or ``assembly_request_id`` (a form
    built from a blueprint) supplies the items; navigation/scoring control delivery.
    """

    administration_model: Literal["linear"] = "linear"
    # A pre-assembled form, or an assembly request to build one from a blueprint.
    form_ref: str | None = None
    assembly_request_id: str | None = None
    navigation: LinearNavigationConfig = Field(default_factory=LinearNavigationConfig)
    scoring: LinearScoringConfig = Field(default_factory=LinearScoringConfig)


class CatConfig(BaseModel):
    """CAT configuration (placeholder fields for Phase 0).

    Phase 2 mirrors the existing CAT platform's TestConfig (selection, estimation,
    stopping incl. SPRT, exposure, content balancing, pre-CAT, neural fusion).
    """

    administration_model: Literal["cat"] = "cat"
    irt_model: str = "2PL"
    max_items: int | None = None


class LoftConfig(BaseModel):
    """LOFT configuration (BP-MODES-1 §4): a unique conforming form is assembled
    per examinee at session start — content constraints + enemy policy exactly as
    fixed form, the TIF tolerance band as a HARD acceptance criterion (§4.1), and
    ``max_exposure_rate`` reinterpreted as a running cap against the exposure
    ledger (§4.2). Delivery/scoring of the assembled form is linear-style."""

    administration_model: Literal["loft"] = "loft"
    #: §4.3 engine: (a) seeded randomized feasibility search with the band
    #: acceptance test, (b) per-session CP-SAT with the band as hard
    #: constraints + a randomized objective for form diversity, or
    #: (c) "pregenerated" — draw from a batch-assembled, human-reviewable form
    #: pool (session context must supply ``form_pool``: the published forms).
    engine: Literal["random_constrained", "cp_sat", "pregenerated"] = (
        "random_constrained"
    )
    #: engine (a): acceptance retries before the session start fails loudly
    max_attempts: int = Field(default=60, ge=1, le=1000)
    #: engine (b): per-session solver budget
    time_limit_s: float = Field(default=5.0, gt=0.0)
    navigation: LinearNavigationConfig = Field(default_factory=LinearNavigationConfig)
    scoring: LinearScoringConfig = Field(default_factory=LinearScoringConfig)


# Extend this union as models land (MstConfig, ...). The discriminator
# lets FastAPI/Orval generate the correct branch automatically.
TestConfig = Annotated[
    LinearConfig | CatConfig | LoftConfig,
    Field(discriminator="administration_model"),
]


class TestConfigEnvelope(BaseModel):
    """Wrapper so OpenAPI exposes the union as a named, addressable schema."""

    config: TestConfig
