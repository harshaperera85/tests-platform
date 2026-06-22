"""Item-parameter normalization onto the canonical theta metric.

Single source of truth for the IRT parameterization (CLAUDE.md golden rule 4).
Every engine that touches IRT parameters or theta goes through this module so the
D-scaling mismatch (catR ``D=1`` vs mirt ``D=1.702``) is handled in exactly one
place.

The canonical metric is the **mirt logistic metric** with ``D = 1.702``: the 2PL/
3PL response function is

    P(theta) = c + (1 - c) / (1 + exp(-D * a * (theta - b)))

Parameters that were calibrated under a different scaling constant ``D_src`` are
rescaled so the *logit* ``D * a * (theta - b)`` is preserved:

    a_canonical = a_src * (D_src / D_canonical)

which leaves the response function (and therefore Fisher information) unchanged.
This makes "normalize to canonical" a no-op on the response surface while pinning
a single ``D`` that the rest of the codebase can assume.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Canonical scaling constant = mirt logistic metric.
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
