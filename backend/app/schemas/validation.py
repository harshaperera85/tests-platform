"""Cross-validation: OR-Tools assembly vs. the R oracle (eatATA), read-only.

The owned OR-Tools engine is the sole production assembler. This compares an
already-assembled form against the established R package on the *same* compiled
problem (same canonical D=1 info matrix, constraints, objective), so a user can
see — as transparent psychometric output — whether the two agree. The R result is
never used to build a deliverable form.
"""

from __future__ import annotations

from pydantic import BaseModel


class CrossValSide(BaseModel):
    """One assembler's solution."""

    item_ids: list[str]
    objective_value: float | None


class CrossValOracle(BaseModel):
    """The R oracle's solution + solve metadata."""

    status: str
    item_ids: list[str] | None = None
    objective_value: float | None = None
    solver: str | None = None
    solve_time_s: float | None = None


class CrossValComparison(BaseModel):
    """Structured agreement between the two solutions."""

    selection_match: bool
    only_in_ortools: list[str]
    only_in_oracle: list[str]
    jaccard: float
    objective_abs_diff: float | None
    objective_within_tolerance: bool | None
    tolerance: float
    tolerance_basis: str
    constraints_satisfied: bool


class CrossValidationResult(BaseModel):
    """Full cross-validation payload for the UI.

    ``status``: ``ok`` (ran and compared), ``unsupported`` (blueprint outside the
    oracle's scope — single-form unweighted minimax only), ``oracle_unavailable``
    (service unreachable), or ``error``.
    """

    status: str
    package: str
    detail: str | None = None
    ortools: CrossValSide
    oracle: CrossValOracle
    comparison: CrossValComparison | None = None
