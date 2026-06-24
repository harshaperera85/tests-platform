"""Difficulty conversion: b=-d/a, SE(b) delta-method (== mirt, not SE(d)), routing."""

from __future__ import annotations

import math

import pytest

from app.psychometrics.difficulty import difficulty_view, synthetic_difficulty
from app.psychometrics.params import ItemParameters

# Known case captured from a real mirt 1.46.1 fit (SE=TRUE), item 1:
#   coef(printSE=TRUE): a1, d (+ vcov);  coef(IRTpars=TRUE, printSE=TRUE): b, SE(b).
# These are the authoritative mirt numbers the R service must reproduce.
KNOWN = {
    "a": 1.337930,
    "d": -0.525263,
    "var_a": 0.00742195,
    "var_d": 0.00204668,
    "cov_ad": -0.00119068,
}
MIRT_B = 0.392594
MIRT_SE_B = 0.035498
MIRT_SE_D = 0.045240


def _delta_se_b(a: float, d: float, va: float, vd: float, cad: float) -> float:
    """Delta-method Var(b)=J Σ Jᵀ, J=[d/a², -1/a] — mirt's IRTpars transform."""
    j1, j2 = d / (a * a), -1.0 / a
    return math.sqrt(j1 * j1 * va + j2 * j2 * vd + 2 * j1 * j2 * cad)


def test_se_b_is_delta_method_equal_to_mirt_not_a_copy_of_se_d() -> None:
    se_b = _delta_se_b(
        KNOWN["a"], KNOWN["d"], KNOWN["var_a"], KNOWN["var_d"], KNOWN["cov_ad"]
    )
    # (i) matches mirt's IRTpars=TRUE SE(b)
    assert se_b == pytest.approx(MIRT_SE_B, abs=1e-4)
    # (ii) is NOT a naive copy of SE(d)
    assert abs(se_b - MIRT_SE_D) > 1e-3
    # (iii) point estimate b = -d/a matches mirt b
    assert -KNOWN["d"] / KNOWN["a"] == pytest.approx(MIRT_B, abs=1e-4)


def test_synthetic_difficulty_has_no_se() -> None:
    it = ItemParameters(item_id="i", a=1.5, d=-0.75)  # b = 0.5
    view = synthetic_difficulty(it)
    assert view.b == pytest.approx(0.5)
    assert view.se_b is None


def test_routing_synthetic_vs_calibrated() -> None:
    it = ItemParameters(item_id="i", a=1.5, d=-0.75)
    assert difficulty_view(it, "synthetic").se_b is None
    # calibrated routing refuses to fabricate SE(b) when covariance is absent
    with pytest.raises(ValueError):
        difficulty_view(it, "calibrated")
