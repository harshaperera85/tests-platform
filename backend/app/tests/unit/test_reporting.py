"""The optional metric reporting transform (presentation only)."""

from __future__ import annotations

import pytest

from app.psychometrics.information import item_information, prob_correct
from app.psychometrics.params import CANONICAL_D, ItemParameters
from app.psychometrics.reporting import (
    NORMAL_OGIVE_D,
    report_difficulty,
    report_discrimination,
    report_information,
    report_theta,
)


def test_canonical_is_logistic_d1() -> None:
    assert CANONICAL_D == 1.0


def test_discrimination_relabel_to_normal_ogive() -> None:
    # canonical (D=1) a -> normal-ogive a' = a * (1 / 1.702)
    assert report_discrimination(1.702) == pytest.approx(1.0)
    assert report_discrimination(1.0, display_d=NORMAL_OGIVE_D) == pytest.approx(
        1.0 / 1.702
    )


def test_theta_difficulty_information_are_invariant() -> None:
    # location + information are invariant under a metric relabel (identity)
    assert report_theta(0.7) == 0.7
    assert report_difficulty(-1.3) == -1.3
    assert report_information(2.5) == 2.5


def test_relabel_preserves_the_response_function() -> None:
    # Reporting a in normal-ogive terms, then reconstructing the logit with D=1.702,
    # reproduces the canonical (D=1) response/information exactly.
    item = ItemParameters(item_id="i", a=1.4, d=-1.4 * 0.3)  # canonical D=1, b=0.3
    a_disp = report_discrimination(item.a, display_d=NORMAL_OGIVE_D)
    for theta in (-1.0, 0.0, 0.5):
        # logit under display metric == logit under canonical metric
        assert NORMAL_OGIVE_D * a_disp * (theta - item.b) == pytest.approx(
            CANONICAL_D * item.a * (theta - item.b)
        )
        # so information computed either way matches
        info_disp = (NORMAL_OGIVE_D * a_disp) ** 2 * prob_correct(
            item, theta
        ) * (1 - prob_correct(item, theta))
        assert info_disp == pytest.approx(item_information(item, theta))
