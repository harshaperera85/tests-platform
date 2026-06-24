"""Unit tests for the canonical metric layer (logistic D=1, slope-intercept)."""

from __future__ import annotations

import math

import pytest

from app.psychometrics.information import (
    item_information,
    prob_correct,
    standard_error,
    tif_curve,
)
from app.psychometrics.information import test_information as tif_value
from app.psychometrics.params import (
    CANONICAL_D,
    ItemParameters,
    normalize_to_canonical,
)
from app.psychometrics.scoring import eap_estimate


def _si(item_id: str, a: float, b: float, **kw: object) -> ItemParameters:
    """Build a canonical slope-intercept item from a difficulty b (d = -a*b)."""
    return ItemParameters(item_id=item_id, a=a, d=-a * b, **kw)  # type: ignore[arg-type]


def test_prob_at_difficulty_is_half_for_2pl() -> None:
    item = _si("i", a=1.3, b=0.4)
    assert prob_correct(item, 0.4) == pytest.approx(0.5)


def test_b_is_minus_d_over_a() -> None:
    item = ItemParameters(item_id="i", a=1.6, d=-0.8)
    assert item.b == pytest.approx(0.5)


def test_2pl_information_peaks_at_difficulty() -> None:
    item = _si("i", a=1.5, b=0.0)
    at_peak = item_information(item, 0.0)
    assert at_peak > item_information(item, 1.0)
    assert at_peak > item_information(item, -1.0)
    # closed form at b: a^2 * 0.25 (D=1)
    assert at_peak == pytest.approx(1.5**2 * 0.25)


def test_3pl_information_general_form_and_reduces_at_c0() -> None:
    # c>0 matches the general 3PL form; c=0 reduces to a^2 P Q.
    it3 = ItemParameters(item_id="g", a=1.2, d=0.3, c=0.2)
    p = prob_correct(it3, 0.5)
    q = 1 - p
    expected = 1.2**2 * (q / p) * ((p - 0.2) / (1 - 0.2)) ** 2
    assert item_information(it3, 0.5) == pytest.approx(expected)

    it2 = ItemParameters(item_id="h", a=1.2, d=0.3, c=0.0)
    p2 = prob_correct(it2, 0.5)
    assert item_information(it2, 0.5) == pytest.approx(1.2**2 * p2 * (1 - p2))


def test_normalization_rescales_noncanonical_d_and_preserves_response() -> None:
    # A normal-ogive (D=1.702) source rescaled onto canonical logistic D=1.
    src_d = 1.702
    raw = ItemParameters(item_id="i", a=1.0, d=-0.2, scaling_d=src_d)  # b = 0.2
    norm = normalize_to_canonical(raw)
    assert norm.scaling_d == CANONICAL_D
    # slope-intercept scales jointly by D_src/D_canon
    assert norm.a == pytest.approx(1.0 * src_d / CANONICAL_D)
    assert norm.d == pytest.approx(-0.2 * src_d / CANONICAL_D)
    assert norm.b == pytest.approx(0.2)  # difficulty invariant to scaling
    for theta in (-1.0, 0.0, 0.7):
        assert prob_correct(raw, theta) == pytest.approx(prob_correct(norm, theta))
        assert item_information(raw, theta) == pytest.approx(
            item_information(norm, theta)
        )


def test_normalization_is_idempotent() -> None:
    item = ItemParameters(item_id="i", a=1.0, d=0.0)
    assert normalize_to_canonical(
        normalize_to_canonical(item)
    ) == normalize_to_canonical(item)


def test_tif_is_sum_of_item_information() -> None:
    items = [_si("a", a=1.0, b=-0.5), _si("b", a=1.2, b=0.5)]
    assert tif_value(items, 0.0) == pytest.approx(
        sum(item_information(i, 0.0) for i in items)
    )
    assert len(tif_curve(items, [-1.0, 0.0, 1.0])) == 3


def test_standard_error_from_information() -> None:
    assert standard_error(4.0) == pytest.approx(0.5)
    assert math.isinf(standard_error(0.0))


def test_eap_recovers_direction_and_prior() -> None:
    items = [
        _si(f"i{k}", a=1.2, b=b) for k, b in enumerate([-1.0, -0.5, 0.0, 0.5, 1.0])
    ]
    high = eap_estimate(items, [1, 1, 1, 1, 1]).theta
    low = eap_estimate(items, [0, 0, 0, 0, 0]).theta
    assert high > 0 > low
    none = eap_estimate([], [])
    assert none.theta == pytest.approx(0.0)
    assert none.standard_error == pytest.approx(1.0)


def test_eap_rejects_bad_inputs() -> None:
    items = [ItemParameters(item_id="i", a=1.0, d=0.0)]
    with pytest.raises(ValueError):
        eap_estimate(items, [1, 0])
    with pytest.raises(ValueError):
        eap_estimate(items, [2])
