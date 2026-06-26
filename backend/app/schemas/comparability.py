"""Schemas for the cross-form comparability / equating-evidence report (L2b).

**Comparability evidence**, NOT statistical equating: this shows whether a set of
forms match *by design* on the IRT scale (TIF / SE / TCC alignment on the canonical
D=1 metric). It does **not** derive score-conversion tables from examinee response
data — that is post-administration equating, a downstream program-level function
requiring real responses, and is out of scope here.
"""

from __future__ import annotations

from pydantic import BaseModel


class ComparabilityRequest(BaseModel):
    form_ids: list[str]
    #: max allowed TIF spread (info units) across forms at any θ before flagging
    tolerance: float = 1.0
    #: max allowed expected-score (TCC) spread across forms at any θ before flagging
    score_tolerance: float = 1.0


class CurvePoint(BaseModel):
    theta: float
    tif: float
    se: float | None  # 1/√I; None when I == 0
    tcc: float  # expected raw score Σ Pᵢ(θ)


class FormSummary(BaseModel):
    form_id: str
    n_items: int
    marginal_reliability: float
    mean_information: float
    peak_information: float
    peak_theta: float
    curve: list[CurvePoint]


class DispersionPoint(BaseModel):
    theta: float
    tif_min: float
    tif_max: float
    tif_spread: float  # max − min across forms
    tif_sd: float
    tcc_spread: float  # max − min expected score across forms
    diverged: bool  # tif_spread > tolerance or tcc_spread > score_tolerance


class TargetPoint(BaseModel):
    theta: float
    target: float


class ComparabilityReport(BaseModel):
    form_ids: list[str]
    n_forms: int
    metric: str = "logistic-D1-slope-intercept"
    theta_grid: list[float]
    tolerance: float
    score_tolerance: float
    #: common design target (from the forms' shared blueprint), if any
    target: list[TargetPoint]
    forms: list[FormSummary]
    dispersion: list[DispersionPoint]
    max_tif_deviation: float
    max_tif_deviation_theta: float
    max_expected_score_diff: float
    max_expected_score_diff_theta: float
    passed: bool
    flags: list[str]
    scope_note: str = (
        "Comparability evidence: forms matched by design on the IRT scale (canonical "
        "D=1). NOT statistical equating — no score-conversion tables are derived from "
        "examinee response data (that is downstream post-administration equating)."
    )
