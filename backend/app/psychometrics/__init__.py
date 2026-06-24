"""Psychometrics: the canonical theta metric layer (CLAUDE.md golden rule 4).

One module owns IRT-parameter normalization, closed-form Fisher information / TIF,
and theta scoring, all on a single pinned metric (:data:`CANONICAL_D` = **logistic
D = 1**, matching mirt/the CAT platform). Every engine that touches theta goes
through here, so any source D-scaling mismatch is handled in exactly one place.
Normal-ogive D=1.702 is an optional reporting transform only (see
:mod:`app.psychometrics.reporting`).
"""

from __future__ import annotations

from app.psychometrics.bank import ItemPool, load_default_pool, load_pool
from app.psychometrics.information import (
    information_matrix,
    item_information,
    prob_correct,
    standard_error,
    test_information,
    tif_curve,
)
from app.psychometrics.params import (
    CANONICAL_D,
    CANONICAL_FORM,
    ItemParameters,
    PoolMetric,
    normalize_to_canonical,
    require_metric,
)
from app.psychometrics.reporting import (
    NORMAL_OGIVE_D,
    report_difficulty,
    report_discrimination,
    report_information,
    report_theta,
)
from app.psychometrics.scoring import ThetaEstimate, eap_estimate

__all__ = [
    "CANONICAL_D",
    "CANONICAL_FORM",
    "NORMAL_OGIVE_D",
    "ItemParameters",
    "ItemPool",
    "PoolMetric",
    "require_metric",
    "ThetaEstimate",
    "eap_estimate",
    "information_matrix",
    "item_information",
    "load_default_pool",
    "load_pool",
    "normalize_to_canonical",
    "prob_correct",
    "report_difficulty",
    "report_discrimination",
    "report_information",
    "report_theta",
    "standard_error",
    "test_information",
    "tif_curve",
]
