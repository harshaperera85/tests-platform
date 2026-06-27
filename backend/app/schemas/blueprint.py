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

import math
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ContentConstraint(BaseModel):
    """A min/max bound on the items satisfying a tag predicate.

    Two ways to target items (an item must match **all** predicates):
    - **Marginal** (one tag dimension): set ``tag_type`` + ``tag_value`` — e.g.
      ``KC=algebra`` or ``Bloom=apply``.
    - **Cross-classified cell** (a content × cognitive table cell): set ``tags`` to a
      mapping of dimension → value — e.g. ``{"KC": "algebra", "Bloom": "apply"}``
      means *algebra AND apply*.

    Bounds are interpreted per ``mode``: ``count`` = absolute item counts;
    ``proportion`` = a fraction in [0, 1] of the form length, resolved to a count by
    the compiler (nearest integer). At least one of ``minimum`` / ``maximum`` set.
    """

    tag_type: str | None = None
    tag_value: str | None = None
    tags: dict[str, str] | None = None
    minimum: float | None = Field(default=None, ge=0)
    maximum: float | None = Field(default=None, ge=0)
    mode: Literal["count", "proportion"] = "count"
    label: str | None = None

    @property
    def predicates(self) -> dict[str, str]:
        """Normalized tag predicates (item must match all)."""
        if self.tags:
            return dict(self.tags)
        if self.tag_type is not None and self.tag_value is not None:
            return {self.tag_type: self.tag_value}
        return {}

    @property
    def key(self) -> str:
        if self.label:
            return self.label
        return " & ".join(f"{k}={v}" for k, v in sorted(self.predicates.items()))

    def _resolve(self, value: float | None, length: int) -> int | None:
        if value is None:
            return None
        return round(value * length) if self.mode == "proportion" else int(value)

    def resolved_minimum(self, length: int) -> int | None:
        return self._resolve(self.minimum, length)

    def resolved_maximum(self, length: int) -> int | None:
        return self._resolve(self.maximum, length)

    @model_validator(mode="after")
    def _check(self) -> ContentConstraint:
        if not self.predicates:
            raise ValueError(
                "content constraint needs tag_type+tag_value or a non-empty tags map"
            )
        if self.minimum is None and self.maximum is None:
            raise ValueError("content constraint needs a minimum and/or a maximum")
        if self.mode == "proportion":
            for v in (self.minimum, self.maximum):
                if v is not None and not (0.0 <= v <= 1.0):
                    raise ValueError("proportion bounds must be in [0, 1]")
        else:  # count
            for v in (self.minimum, self.maximum):
                if v is not None and float(v) != int(v):
                    raise ValueError("count bounds must be whole numbers")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError(f"minimum ({self.minimum}) > maximum ({self.maximum})")
        return self


class TIFTarget(BaseModel):
    """Target test information at a set of theta points.

    ``method`` selects the assembly objective: ``minimax`` (drive actual TIF to the
    target, minimizing the worst-point absolute miss — the default for parallel
    forms) or ``maximin`` (maximize information at the worst theta point — there is
    **no target** under maximin, so ``target_info``/``tolerance``/``weights`` are
    ignored). ``tolerance`` is an optional absolute band; when set, the compiler adds
    hard ``|actual - target| <= tolerance`` constraints in addition to the objective.

    ``weights`` (minimax only) give a per-theta multiplier on the deviation term, so
    the objective minimizes ``max_k w_k·|TIF_k − target_k|``. Default all 1.0 (exactly
    the unweighted minimax). Raise a point's weight to **protect fit there** (e.g. a
    cut score) when the pool forces tradeoffs — orthogonal to target height: height
    sets the desired curve *shape*; weight sets *where not to compromise*.
    """

    theta_points: list[float] = Field(min_length=1)
    target_info: list[float] = Field(min_length=1)
    method: Literal["minimax", "maximin"] = "minimax"
    tolerance: float | None = Field(default=None, gt=0.0)
    weights: list[float] | None = Field(default=None)

    @model_validator(mode="after")
    def _check_lengths(self) -> TIFTarget:
        if len(self.theta_points) != len(self.target_info):
            raise ValueError("theta_points and target_info must be the same length")
        if any(v < 0 for v in self.target_info):
            raise ValueError("target_info values must be non-negative")
        if self.weights is not None:
            if len(self.weights) != len(self.theta_points):
                raise ValueError("weights must match the number of theta_points")
            if any(w <= 0 for w in self.weights):
                raise ValueError("weights must be positive")
        return self

    @property
    def resolved_weights(self) -> tuple[float, ...]:
        """Per-theta weights, defaulting to all 1.0 (unweighted minimax)."""
        if self.weights is None:
            return tuple(1.0 for _ in self.theta_points)
        return tuple(self.weights)


class EnemyPolicy(BaseModel):
    """How to honor ``enemy_of`` relations from the bank.

    When ``enforce`` is true, two items that are enemies of each other may not both
    appear in the same form (declared one-directionally in the bank; the compiler
    symmetrizes).
    """

    enforce: bool = True


class ExposureTarget(BaseModel):
    """Optional caps on item reuse across assembled forms (multi-form jobs).

    Two reuse levers:
    - **per-item use cap**: an item appears in at most ``max_use_per_item`` forms.
      Specify it directly, or as a target ``max_exposure_rate`` (proportion 0–1) that
      the compiler translates to a count given the planned form count:
      ``max_use ≈ ceil(rate × num_forms)`` (assumes **uniform form administration**).
      A raw ``max_use_per_item`` is the low-level override and wins if both are set.
    - **pairwise overlap cap**: any two forms may share at most
      ``max_pairwise_overlap`` items (distinct from the total per-item cap — it bounds
      similarity *between forms*, e.g. for security across parallel administrations).
    """

    max_use_per_item: int | None = Field(default=None, ge=1)
    max_exposure_rate: float | None = Field(default=None, gt=0.0, le=1.0)
    max_pairwise_overlap: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_any(self) -> ExposureTarget:
        if (
            self.max_use_per_item is None
            and self.max_exposure_rate is None
            and self.max_pairwise_overlap is None
        ):
            raise ValueError(
                "exposure_target needs at least one of max_use_per_item, "
                "max_exposure_rate, max_pairwise_overlap"
            )
        return self

    def resolved_max_use(self, num_forms: int) -> int | None:
        """Per-item use cap as a count: raw override, else rate × num_forms."""
        if self.max_use_per_item is not None:
            return self.max_use_per_item
        if self.max_exposure_rate is not None:
            return math.ceil(self.max_exposure_rate * num_forms)
        return None


class ExposureFeedback(BaseModel):
    """**Opt-in, default-off** feedback from *longitudinal* item-exposure history into
    assembly eligibility.

    Distinct from :class:`ExposureTarget` (within-batch overlap/use/rate, governing a
    single multi-form assembly) and from CAT administration-time exposure control
    (Sympson-Hetter etc.). Uses cumulative usage *across* past assemblies/publications:
    - ``max_cumulative`` — hard-exclude items already used at least this many times
      (over-exposure control).
    - ``prefer_underused`` + ``underuse_weight`` — bias selection toward under-utilized
      items (bidirectional utilization). ``underuse_weight`` is in objective info-units
      per unit of cumulative exposure: small = tie-breaker, large = strong preference.

    When this is absent the assembly is **byte-for-byte unchanged** (no eligibility
    constraints/terms are added).
    """

    count_contexts: list[str] = Field(default_factory=lambda: ["published"])
    max_cumulative: int | None = Field(default=None, ge=1)
    prefer_underused: bool = False
    underuse_weight: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _check(self) -> ExposureFeedback:
        if self.max_cumulative is None and not (
            self.prefer_underused and self.underuse_weight > 0
        ):
            raise ValueError(
                "exposure_feedback needs max_cumulative and/or "
                "(prefer_underused with underuse_weight > 0)"
            )
        return self


class Blueprint(BaseModel):
    """Full assembly specification for one (or several parallel) forms."""

    name: str = "untitled-blueprint"
    length: int = Field(gt=0, description="items per form")
    num_forms: int = Field(default=1, ge=1)
    content_constraints: list[ContentConstraint] = Field(default_factory=list)
    statistical_target: TIFTarget
    enemy_policy: EnemyPolicy = Field(default_factory=EnemyPolicy)
    exposure_target: ExposureTarget | None = None
    #: opt-in longitudinal-exposure eligibility feedback (default-off)
    exposure_feedback: ExposureFeedback | None = None

    @model_validator(mode="after")
    def _check_feasible_shape(self) -> Blueprint:
        # Cheap structural feasibility: a single tag minimum (resolved to a count)
        # can't exceed the length; the rest is left to the solver.
        for c in self.content_constraints:
            mn = c.resolved_minimum(self.length)
            if mn is not None and mn > self.length:
                raise ValueError(
                    f"constraint {c.key} minimum {mn} exceeds form length {self.length}"
                )
        return self
