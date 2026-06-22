"""Psychometrics: the canonical theta metric layer (CLAUDE.md golden rule 4).

One module owns IRT-parameter normalization, closed-form Fisher information / TIF,
and theta scoring, all on a single pinned metric (:data:`CANONICAL_D`). Every
engine that touches theta goes through here, so the catR/mirt D-scaling mismatch is
handled in exactly one place.
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
    ItemParameters,
    normalize_to_canonical,
)
from app.psychometrics.scoring import ThetaEstimate, eap_estimate

__all__ = [
    "CANONICAL_D",
    "ItemParameters",
    "ItemPool",
    "ThetaEstimate",
    "eap_estimate",
    "information_matrix",
    "item_information",
    "load_default_pool",
    "load_pool",
    "normalize_to_canonical",
    "prob_correct",
    "standard_error",
    "test_information",
    "tif_curve",
]
