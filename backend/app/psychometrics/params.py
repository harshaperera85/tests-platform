"""Item-parameter normalization onto the canonical theta metric.

Single source of truth for the IRT parameterization (CLAUDE.md golden rule 4).
Every engine that touches IRT parameters or theta goes through this module so any
D-scaling mismatch between calibration sources is handled in exactly one place.

The 2PL/3PL response function used everywhere is

    P(theta) = c + (1 - c) / (1 + exp(-D * a * (theta - b)))

``CANONICAL_D`` is **our** chosen scaling constant for that ``D`` (currently 1.702,
the normal-ogive-equivalent convention). It is NOT inherited from mirt:

    EMPIRICAL FACT (verified against mirt 1.46.1 / R 4.4.2 — the exact pin the CAT
    platform's mirtcat-service uses): mirt computes information in the **logistic
    metric with D = 1** (no 1.702). A 2PL with a=1, b=0 has iteminfo(theta=0) =
    0.25 = a^2 * P * Q, and P(theta=1) = 1/(1+exp(-1)) = 0.731 exactly — not the
    D=1.702 value 0.846. mirt's ``coef(IRTpars=TRUE)`` is only a slope/intercept
    (a1, d) -> discrimination/difficulty (a = a1, b = -d/a1) reparameterization,
    leaving ``a`` unchanged, so it introduces no scaling constant either.

Implication: the CAT platform (params passed straight to mirt, nothing set) works
in the **D = 1** metric while this constant is 1.702. The two are reconciled by
:func:`normalize_to_canonical`: parameters calibrated under a different ``D_src``
(e.g. mirt items, ``D_src = 1``) are rescaled so the *logit* ``D * a * (theta - b)``
is preserved:

    a_canonical = a_src * (D_src / D_canonical)

which leaves the response function (and therefore Fisher information and theta)
unchanged. So correctness only requires every incoming item to carry its TRUE
estimation ``scaling_d`` (mirt/CAT items => 1.0). See ``docs/backlog.md`` for the
open decision to make D = 1 the canonical value when the CAT/mirt scoring service
or a real item bank is wired in (deferred: flipping it now only rescales simulated
demo numbers and would churn tests/docs for no functional gain).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Canonical scaling constant for THIS platform's metric. NOTE: this is OUR
#: convention, not mirt's — mirt (and thus the CAT platform) uses D = 1 (verified
#: empirically against mirt 1.46.1). Cross-D items are reconciled by
#: normalize_to_canonical; see this module's docstring and docs/backlog.md.
CANONICAL_D: float = 1.702


class ItemParameters(BaseModel):
    """Calibrated IRT parameters for one item, plus the metadata assembly needs.

    ``scaling_d`` records the constant under which ``a`` is expressed. After
    :func:`normalize_to_canonical` it always equals :data:`CANONICAL_D`.
    """

    model_config = ConfigDict(frozen=True)

    item_id: str
    a: float = Field(gt=0.0, description="discrimination (on this item's scaling_d)")
    b: float = Field(description="difficulty / location on theta")
    c: float = Field(default=0.0, ge=0.0, lt=1.0, description="lower asymptote")
    scaling_d: float = Field(default=CANONICAL_D, gt=0.0)
    tags: dict[str, str] = Field(default_factory=dict)
    enemy_of: tuple[str, ...] = ()

    @field_validator("enemy_of", mode="before")
    @classmethod
    def _coerce_enemy(cls, v: object) -> tuple[str, ...]:
        if v is None:
            return ()
        if isinstance(v, str):
            return (v,)
        return tuple(v)  # type: ignore[arg-type]


def normalize_to_canonical(item: ItemParameters) -> ItemParameters:
    """Return ``item`` with discrimination rescaled onto :data:`CANONICAL_D`.

    Preserves the response function exactly. Idempotent: already-canonical items
    are returned unchanged.
    """
    if item.scaling_d == CANONICAL_D:
        return item
    a_canonical = item.a * (item.scaling_d / CANONICAL_D)
    return item.model_copy(update={"a": a_canonical, "scaling_d": CANONICAL_D})
