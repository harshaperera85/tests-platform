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


# Extend this union as models land (LoftConfig, MstConfig, ...). The discriminator
# lets FastAPI/Orval generate the correct branch automatically.
TestConfig = Annotated[
    LinearConfig | CatConfig,
    Field(discriminator="administration_model"),
]


class TestConfigEnvelope(BaseModel):
    """Wrapper so OpenAPI exposes the union as a named, addressable schema."""

    config: TestConfig
