"""Theta scoring on the canonical metric.

The canonical source of truth for theta is the mirt scoring service (CLAUDE.md
golden rule 4). That service is a stub in Phase 0/1, so for Linear fixed-form
scoring we compute EAP locally in closed form on the **same** canonical metric
(:data:`CANONICAL_D`) — identical parameterization, no separate scale. When the
mirt service comes online (Phase 2) Linear can delegate to it through this module
without changing the contract.

EAP uses fixed Gauss–Hermite-style rectangular quadrature over a standard-normal
prior, which is accurate and fully deterministic (important for tests and audit).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.psychometrics.information import prob_correct
from app.psychometrics.params import ItemParameters


@dataclass(frozen=True)
class ThetaEstimate:
    theta: float
    standard_error: float
    method: str = "eap"


def _quadrature(n_points: int, lo: float, hi: float) -> tuple[list[float], list[float]]:
    """Rectangular nodes/weights for a standard-normal prior on ``[lo, hi]``."""
    step = (hi - lo) / (n_points - 1)
    nodes = [lo + i * step for i in range(n_points)]
    # Unnormalized normal density; weights are normalized below by the caller.
    dens = [math.exp(-0.5 * x * x) for x in nodes]
    total = sum(dens) or 1.0
    weights = [d / total for d in dens]
    return nodes, weights


def eap_estimate(
    items: Sequence[ItemParameters],
    responses: Sequence[int],
    *,
    n_points: int = 61,
    bounds: tuple[float, float] = (-4.0, 4.0),
) -> ThetaEstimate:
    """Expected a posteriori theta + posterior SD for a response vector.

    ``responses[i]`` is 1 (correct) / 0 (incorrect) for ``items[i]``. With no
    administered items the estimate is the prior mean (0) and SD (1).
    """
    if len(items) != len(responses):
        raise ValueError("items and responses must be the same length")
    nodes, prior = _quadrature(n_points, *bounds)

    if not items:
        return ThetaEstimate(theta=0.0, standard_error=1.0)

    posterior = list(prior)
    for item, u in zip(items, responses, strict=True):
        if u not in (0, 1):
            raise ValueError(f"response must be 0 or 1, got {u!r}")
        for k, theta in enumerate(nodes):
            p = prob_correct(item, theta)
            posterior[k] *= p if u == 1 else (1.0 - p)

    norm = sum(posterior)
    if norm <= 0.0:
        # Degenerate likelihood (shouldn't happen with 0<P<1); fall back to prior.
        return ThetaEstimate(theta=0.0, standard_error=1.0)

    mean = sum(theta * w for theta, w in zip(nodes, posterior, strict=True)) / norm
    var = (
        sum((theta - mean) ** 2 * w for theta, w in zip(nodes, posterior, strict=True))
        / norm
    )
    return ThetaEstimate(theta=mean, standard_error=math.sqrt(max(var, 0.0)))
