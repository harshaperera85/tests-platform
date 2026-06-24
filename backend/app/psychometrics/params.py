"""Item-parameter normalization onto the canonical theta metric.

Single source of truth for the IRT parameterization (CLAUDE.md golden rule 4).
Every engine that touches IRT parameters or theta goes through this module, and any
source that differs on either axis is reconciled here, at exactly one chokepoint.

Two **orthogonal** axes, both pinned to mirt 1.46.1's native metric:

* **Axis 1 — scaling:** logistic, ``D = 1``. The response function is
  ``P(theta) = c + (1 - c) * sigma(a * theta + d)``, ``sigma(x) = 1/(1+e^-x)``.
  No 1.702 ever enters computation; normal-ogive ``D = 1.702`` is a *reporting*
  transform only (see :mod:`app.psychometrics.reporting`). Verified empirically:
  a=1, d=0 -> info(0)=0.25, P(1)=0.731 (not the D=1.702 values).
* **Axis 2 — parameterization form:** **slope-intercept ``(a, d)`` is canonical**
  (matches mirt's storage). Traditional ``(a, b)`` with ``b = -d / a`` is the
  *difficulty view*. Point-estimate-only (synthetic) pools may take ``b = -d/a``
  in Python; **standard errors for ``b`` must come from mirt's ``IRTpars=TRUE``
  delta-method path** (see ``engines/scoring-r``), never a one-variable shortcut.

``Fisher information`` (in :mod:`app.psychometrics.information`):
``I(theta) = a^2 * (Q/P) * ((P - c)/(1 - c))^2``, reducing to ``a^2 * P * Q`` at c=0.

Every ingested pool MUST declare its metric (:class:`PoolMetric`): ``scaling_d``,
``form`` (axis 2), and ``kind`` (synthetic vs calibrated). Undeclared metric is an
error — there is no silent default (see :func:`require_metric`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Canonical scaling constant: logistic D=1 (mirt 1.46.1 / the CAT platform).
CANONICAL_D: float = 1.0

#: Parameterization-form axis.
Form = Literal["slope_intercept", "traditional"]
#: Canonical parameterization form: slope-intercept (a, d), mirt-native.
CANONICAL_FORM: Form = "slope_intercept"

#: Whether a pool carries calibration uncertainty.
PoolKind = Literal["synthetic", "calibrated"]

#: Tolerance for the on-load b ≈ -d/a consistency check.
B_CONSISTENCY_TOL: float = 1e-6


class PoolMetric(BaseModel):
    """The metric contract a pool must declare (no silent defaults).

    ``scaling_d`` = axis 1; ``form`` = axis 2; ``kind`` records whether items carry
    standard errors / covariance (``calibrated``) or are point estimates only
    (``synthetic``), which routes difficulty-SE conversion.
    """

    model_config = ConfigDict(frozen=True)

    scaling_d: float = Field(gt=0.0)
    form: Form
    kind: PoolKind


def require_metric(raw: dict | None, *, where: str) -> PoolMetric:
    """Parse a declared metric block or raise — never default silently."""
    if not raw:
        raise ValueError(
            f"{where}: pool has no declared metric. Every pool must declare "
            "{scaling_d, form, kind}; refusing to assume a default."
        )
    missing = {"scaling_d", "form", "kind"} - set(raw)
    if missing:
        raise ValueError(
            f"{where}: pool metric is missing required keys {sorted(missing)}."
        )
    return PoolMetric(scaling_d=raw["scaling_d"], form=raw["form"], kind=raw["kind"])


class ItemParameters(BaseModel):
    """Calibrated IRT parameters for one item on the **canonical** metric.

    Stored slope-intercept: ``a`` (discrimination), ``d`` (intercept), ``c`` (mirt
    ``g``, lower asymptote), ``u`` (upper asymptote). The difficulty view ``b`` is
    derived (``-d/a``). ``scaling_d`` always equals :data:`CANONICAL_D` after
    :func:`normalize_to_canonical`.

    Calibrated items may carry ``se_a``/``se_d``/``cov_ad`` (parameter covariance)
    and an mirt-propagated ``se_b``. Synthetic items leave these ``None`` — Python
    never fabricates ``se_b`` from ``a``/``d`` alone.
    """

    model_config = ConfigDict(frozen=True)

    item_id: str
    a: float = Field(gt=0.0, description="discrimination (D=1 logistic slope)")
    d: float = Field(description="intercept (slope-intercept form)")
    c: float = Field(default=0.0, ge=0.0, lt=1.0, description="lower asymptote (g)")
    u: float = Field(default=1.0, gt=0.0, le=1.0, description="upper asymptote (u)")
    scaling_d: float = Field(default=CANONICAL_D, gt=0.0)
    tags: dict[str, str] = Field(default_factory=dict)
    enemy_of: tuple[str, ...] = ()
    # calibration uncertainty (calibrated pools only)
    se_a: float | None = Field(default=None, ge=0.0)
    se_d: float | None = Field(default=None, ge=0.0)
    cov_ad: float | None = None
    se_b: float | None = Field(default=None, ge=0.0)

    @property
    def b(self) -> float:
        """Difficulty view: ``b = -d / a`` (location on theta)."""
        return -self.d / self.a

    @model_validator(mode="before")
    @classmethod
    def _coerce_enemy(cls, data: object) -> object:
        if isinstance(data, dict) and "enemy_of" in data:
            v = data["enemy_of"]
            if v is None:
                data["enemy_of"] = ()
            elif isinstance(v, str):
                data["enemy_of"] = (v,)
        return data


def normalize_to_canonical(item: ItemParameters) -> ItemParameters:
    """Return ``item`` rescaled onto :data:`CANONICAL_D` (axis 1).

    Slope-intercept scales jointly: a logit ``D_src * (a*theta + d)`` is preserved by
    ``a -> a * (D_src/D_canon)`` and ``d -> d * (D_src/D_canon)`` (so ``b = -d/a`` is
    invariant). Form conversion (axis 2) is handled at ingest, not here. Idempotent.
    """
    if item.scaling_d == CANONICAL_D:
        return item
    k = item.scaling_d / CANONICAL_D
    return item.model_copy(
        update={
            "a": item.a * k,
            "d": item.d * k,
            "scaling_d": CANONICAL_D,
            "se_a": None if item.se_a is None else item.se_a * k,
            "se_d": None if item.se_d is None else item.se_d * k,
            "cov_ad": None if item.cov_ad is None else item.cov_ad * k * k,
        }
    )
