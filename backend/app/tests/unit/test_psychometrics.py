"""Unit tests for the canonical metric layer."""

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


def test_prob_at_difficulty_is_half_for_2pl() -> None:
    item = ItemParameters(item_id="i", a=1.3, b=0.4)
    assert prob_correct(item, 0.4) == pytest.approx(0.5)


def test_2pl_information_peaks_at_difficulty() -> None:
    item = ItemParameters(item_id="i", a=1.5, b=0.0)
    at_peak = item_information(item, 0.0)
    assert at_peak > item_information(item, 1.0)
    assert at_peak > item_information(item, -1.0)
    # closed form at b: D^2 a^2 * 0.25
    expected = (CANONICAL_D * 1.5) ** 2 * 0.25
    assert at_peak == pytest.approx(expected)


def test_normalization_preserves_response_and_information() -> None:
    raw = ItemParameters(item_id="i", a=1.0, b=0.2, scaling_d=1.0)
    norm = normalize_to_canonical(raw)
    assert norm.scaling_d == CANONICAL_D
    assert norm.a == pytest.approx(1.0 / CANONICAL_D)
    for theta in (-1.0, 0.0, 0.7):
        assert prob_correct(raw, theta) == pytest.approx(prob_correct(norm, theta))
        assert item_information(raw, theta) == pytest.approx(
            item_information(norm, theta)
        )


def test_normalization_is_idempotent() -> None:
    item = ItemParameters(item_id="i", a=1.0, b=0.0)
    assert normalize_to_canonical(
        normalize_to_canonical(item)
    ) == normalize_to_canonical(item)


def test_tif_is_sum_of_item_information() -> None:
    items = [
        ItemParameters(item_id="a", a=1.0, b=-0.5),
        ItemParameters(item_id="b", a=1.2, b=0.5),
    ]
    assert tif_value(items, 0.0) == pytest.approx(
        sum(item_information(i, 0.0) for i in items)
    )
    curve = tif_curve(items, [-1.0, 0.0, 1.0])
    assert len(curve) == 3


def test_standard_error_from_information() -> None:
    assert standard_error(4.0) == pytest.approx(0.5)
    assert math.isinf(standard_error(0.0))


def test_eap_recovers_direction_and_prior() -> None:
    items = [
        ItemParameters(item_id=f"i{k}", a=1.2, b=b)
        for k, b in enumerate([-1.0, -0.5, 0.0, 0.5, 1.0])
    ]
    high = eap_estimate(items, [1, 1, 1, 1, 1]).theta
    low = eap_estimate(items, [0, 0, 0, 0, 0]).theta
    assert high > 0 > low
    none = eap_estimate([], [])
    assert none.theta == pytest.approx(0.0)
    assert none.standard_error == pytest.approx(1.0)


def test_eap_rejects_bad_inputs() -> None:
    items = [ItemParameters(item_id="i", a=1.0, b=0.0)]
    with pytest.raises(ValueError):
        eap_estimate(items, [1, 0])
    with pytest.raises(ValueError):
        eap_estimate(items, [2])
