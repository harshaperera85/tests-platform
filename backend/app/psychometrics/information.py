"""Closed-form Fisher information and the Test Information Function (TIF).

All computation is on the canonical metric: **logistic D=1, slope-intercept** (see
:mod:`app.psychometrics.params`). Items are normalized via
:func:`normalize_to_canonical` first, so callers never deal with scaling here.

Response function (slope-intercept, D=1):

    P(theta) = c + (1 - c) * sigma(a * theta + d),   sigma(x) = 1 / (1 + e^-x)

Fisher information (3PL; the 2PL is the ``c = 0`` special case):

    I(theta) = a^2 * (Q / P) * ((P - c) / (1 - c))^2,   Q = 1 - P

which reduces to ``I = a^2 * P * Q`` at ``c = 0``. No 1.702 factor anywhere.
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
    """P(correct | theta) on the canonical metric (slope-intercept, D=1)."""
    it = normalize_to_canonical(item)
    p_star = _logistic(it.a * theta + it.d)
    return it.c + (1.0 - it.c) * p_star


def item_information(item: ItemParameters, theta: float) -> float:
    """Fisher information contributed by one item at ``theta``."""
    it = normalize_to_canonical(item)
    p = prob_correct(it, theta)
    q = 1.0 - p
    if p <= 0.0 or q <= 0.0:
        return 0.0
    if it.c == 0.0:
        return it.a * it.a * p * q
    ratio = (p - it.c) / (1.0 - it.c)
    return it.a * it.a * (q / p) * ratio * ratio


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
