"""The Blueprint: a model-independent assembly specification (plan §5, §6).

A blueprint carries **both** a content target (min/max counts by tag — KC, Bloom,
TIMSS, domain) **and** a statistical target (a TIF curve: target information at a
set of theta points). The statistical target is what makes parallel / LOFT / MST
forms psychometrically equivalent rather than merely content-matched.

This object is consumed by the blueprint compiler (``assembly/blueprint_compiler``)
which turns it into a solver-ready constraint set + objective. It is intentionally
free of any administration-model coupling.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ContentConstraint(BaseModel):
    """A min/max count of items carrying a given tag value.

    ``tag_type`` is the tag dimension (e.g. ``"KC"``, ``"Bloom"``, ``"TIMSS"``,
    ``"domain"``); ``tag_value`` is the required value on that dimension. At least
    one of ``minimum`` / ``maximum`` must be set.
    """

    tag_type: str
    tag_value: str
    minimum: int | None = Field(default=None, ge=0)
    maximum: int | None = Field(default=None, ge=0)
    label: str | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> ContentConstraint:
        if self.minimum is None and self.maximum is None:
            raise ValueError("content constraint needs a minimum and/or a maximum")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError(
                f"minimum ({self.minimum}) > maximum ({self.maximum}) "
                f"for {self.tag_type}={self.tag_value}"
            )
        return self

    @property
    def key(self) -> str:
        return self.label or f"{self.tag_type}={self.tag_value}"


class TIFTarget(BaseModel):
    """Target test information at a set of theta points.

    ``method`` selects the assembly objective: ``minimax`` (drive actual TIF to the
    target, minimizing the worst-point absolute miss — the default for parallel
    forms) or ``maximin`` (maximize information at the worst theta point, using
    ``target_info`` as a floor). ``tolerance`` is an optional absolute band; when
    set, the compiler adds hard ``|actual - target| <= tolerance`` constraints in
    addition to the objective.
    """

    theta_points: list[float] = Field(min_length=1)
    target_info: list[float] = Field(min_length=1)
    method: Literal["minimax", "maximin"] = "minimax"
    tolerance: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def _check_lengths(self) -> TIFTarget:
        if len(self.theta_points) != len(self.target_info):
            raise ValueError("theta_points and target_info must be the same length")
        if any(v < 0 for v in self.target_info):
            raise ValueError("target_info values must be non-negative")
        return self


class EnemyPolicy(BaseModel):
    """How to honor ``enemy_of`` relations from the bank.

    When ``enforce`` is true, two items that are enemies of each other may not both
    appear in the same form (declared one-directionally in the bank; the compiler
    symmetrizes).
    """

    enforce: bool = True


class ExposureTarget(BaseModel):
    """Optional cap on how often an item may be used across assembled forms.

    Only meaningful when assembling multiple parallel forms in one job.
    """

    max_use_per_item: int = Field(ge=1)


class Blueprint(BaseModel):
    """Full assembly specification for one (or several parallel) forms."""

    name: str = "untitled-blueprint"
    length: int = Field(gt=0, description="items per form")
    num_forms: int = Field(default=1, ge=1)
    content_constraints: list[ContentConstraint] = Field(default_factory=list)
    statistical_target: TIFTarget
    enemy_policy: EnemyPolicy = Field(default_factory=EnemyPolicy)
    exposure_target: ExposureTarget | None = None

    @model_validator(mode="after")
    def _check_feasible_shape(self) -> Blueprint:
        # Cheap structural feasibility: per-tag minimums can't exceed the length,
        # and the sum of mutually-exclusive-looking minimums is left to the solver.
        for c in self.content_constraints:
            if c.minimum is not None and c.minimum > self.length:
                raise ValueError(
                    f"constraint {c.key} minimum {c.minimum} exceeds form length "
                    f"{self.length}"
                )
        return self
