"""Closed-form Fisher information and the Test Information Function (TIF).

All computation is on the canonical theta metric (:data:`CANONICAL_D`). Items are
normalized via :func:`normalize_to_canonical` before their information is used, so
callers never have to think about scaling here.

For the 3PL (the 2PL is the ``c = 0`` special case) item Fisher information is

    I(theta) = D^2 a^2 * (Q / P) * ((P - c) / (1 - c))^2

with ``P = c + (1 - c) * logistic(D a (theta - b))`` and ``Q = 1 - P``. For the
2PL this collapses to the familiar ``I = D^2 a^2 P (1 - P)``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from app.psychometrics.params import ItemParameters, normalize_to_canonical


def _logistic(z: float) -> float:
    # Numerically stable logistic.
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def prob_correct(item: ItemParameters, theta: float) -> float:
    """P(correct | theta) on the canonical metric."""
    it = normalize_to_canonical(item)
    p_star = _logistic(it.scaling_d * it.a * (theta - it.b))
    return it.c + (1.0 - it.c) * p_star


def item_information(item: ItemParameters, theta: float) -> float:
    """Fisher information contributed by one item at ``theta``."""
    it = normalize_to_canonical(item)
    p = prob_correct(it, theta)
    q = 1.0 - p
    if p <= 0.0 or q <= 0.0:
        return 0.0
    da = it.scaling_d * it.a
    if it.c == 0.0:
        return da * da * p * q
    ratio = (p - it.c) / (1.0 - it.c)
    return da * da * (q / p) * ratio * ratio


def test_information(items: Iterable[ItemParameters], theta: float) -> float:
    """TIF value at one ``theta`` = sum of item informations."""
    return sum(item_information(it, theta) for it in items)


def tif_curve(
    items: Sequence[ItemParameters], theta_points: Sequence[float]
) -> list[float]:
    """TIF evaluated at each theta point."""
    return [test_information(items, t) for t in theta_points]


def information_matrix(
    items: Sequence[ItemParameters], theta_points: Sequence[float]
) -> list[list[float]]:
    """Per-item information, indexed ``[item_index][theta_index]``.

    This is the raw input the assembly engine turns into its TIF objective.
    """
    return [[item_information(it, t) for t in theta_points] for it in items]


def standard_error(info: float) -> float:
    """SEM at a theta from a TIF value: ``1 / sqrt(I)`` (inf when ``I == 0``)."""
    if info <= 0.0:
        return math.inf
    return 1.0 / math.sqrt(info)
