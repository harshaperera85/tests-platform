"""Cross-form comparability / equating-evidence report (L2b, model-agnostic).

Given a set of assembled forms (a test's forms, or a selected group), demonstrate —
on the canonical **logistic D=1 slope-intercept** metric — whether they are
statistically interchangeable *by design*: overlaid TIF, conditional SE, and TCC
(expected score), with per-θ dispersion across forms and pass/flag against a
tolerance. This is the across-forms evidence artifact consulted at the
psychometric-review gate, alongside the per-form QA report (L2a).

Scope: comparability evidence only — NOT response-data equating (see the schema's
scope_note).
"""

from __future__ import annotations

import statistics

from sqlalchemy.orm import Session

from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics import pools
from app.psychometrics.information import (
    prob_correct,
    standard_error,
    test_information,
)
from app.psychometrics.scoring import _quadrature
from app.schemas.blueprint import Blueprint
from app.schemas.comparability import (
    ComparabilityReport,
    CurvePoint,
    DispersionPoint,
    FormSummary,
    TargetPoint,
)

#: θ grid for the overlay curves + dispersion (matches the form-QA grid).
_THETA_GRID = [round(-3.0 + 0.5 * i, 3) for i in range(13)]


def _marginal_reliability(items) -> float:
    nodes, weights = _quadrature(41, -4.0, 4.0)
    err_var = 0.0
    for theta, w in zip(nodes, weights, strict=True):
        info = test_information(items, theta)
        err_var += w * (1.0 / info if info > 1e-9 else 1e6)
    return max(0.0, min(1.0, 1.0 - err_var))


def _form_summary(form: FormRow) -> FormSummary:
    items = pools.load_pool_by_id(form.pool_id).subset(form.item_ids)
    curve: list[CurvePoint] = []
    peak_info, peak_theta = -1.0, 0.0
    info_sum = 0.0
    for theta in _THETA_GRID:
        info = test_information(items, theta)
        se = standard_error(info)
        curve.append(
            CurvePoint(
                theta=theta,
                tif=info,
                se=None if se == float("inf") else se,
                tcc=sum(prob_correct(it, theta) for it in items),
            )
        )
        info_sum += info
        if info > peak_info:
            peak_info, peak_theta = info, theta
    return FormSummary(
        form_id=form.id,
        n_items=len(form.item_ids),
        marginal_reliability=_marginal_reliability(items),
        mean_information=info_sum / len(_THETA_GRID),
        peak_information=peak_info,
        peak_theta=peak_theta,
        curve=curve,
    )


def build_comparability_report(
    db: Session,
    forms: list[FormRow],
    *,
    tolerance: float = 1.0,
    score_tolerance: float = 1.0,
) -> ComparabilityReport:
    summaries = [_form_summary(f) for f in forms]

    # common design target (from the first form's blueprint, if present)
    target: list[TargetPoint] = []
    bp_row = db.get(BlueprintRow, forms[0].blueprint_id) if forms else None
    if bp_row is not None:
        t = Blueprint.model_validate(bp_row.spec).statistical_target
        target = [
            TargetPoint(theta=th, target=tg)
            for th, tg in zip(t.theta_points, t.target_info, strict=False)
        ]

    # per-θ dispersion across forms (index aligns with _THETA_GRID)
    dispersion: list[DispersionPoint] = []
    max_tif_dev, max_tif_theta = 0.0, 0.0
    max_score_diff, max_score_theta = 0.0, 0.0
    flags: list[str] = []
    for k, theta in enumerate(_THETA_GRID):
        tifs = [s.curve[k].tif for s in summaries]
        tccs = [s.curve[k].tcc for s in summaries]
        tif_spread = (max(tifs) - min(tifs)) if tifs else 0.0
        tcc_spread = (max(tccs) - min(tccs)) if tccs else 0.0
        tif_sd = statistics.pstdev(tifs) if len(tifs) > 1 else 0.0
        diverged = tif_spread > tolerance or tcc_spread > score_tolerance
        dispersion.append(
            DispersionPoint(
                theta=theta,
                tif_min=min(tifs) if tifs else 0.0,
                tif_max=max(tifs) if tifs else 0.0,
                tif_spread=tif_spread,
                tif_sd=tif_sd,
                tcc_spread=tcc_spread,
                diverged=diverged,
            )
        )
        if tif_spread > max_tif_dev:
            max_tif_dev, max_tif_theta = tif_spread, theta
        if tcc_spread > max_score_diff:
            max_score_diff, max_score_theta = tcc_spread, theta

    if max_tif_dev > tolerance:
        flags.append(
            f"TIF differs by {max_tif_dev:.2f} info units at θ={max_tif_theta} "
            f"(> tolerance {tolerance})"
        )
    if max_score_diff > score_tolerance:
        flags.append(
            f"expected score differs by {max_score_diff:.2f} points at "
            f"θ={max_score_theta} (> tolerance {score_tolerance})"
        )

    passed = max_tif_dev <= tolerance and max_score_diff <= score_tolerance
    return ComparabilityReport(
        form_ids=[f.id for f in forms],
        n_forms=len(forms),
        theta_grid=list(_THETA_GRID),
        tolerance=tolerance,
        score_tolerance=score_tolerance,
        target=target,
        forms=summaries,
        dispersion=dispersion,
        max_tif_deviation=max_tif_dev,
        max_tif_deviation_theta=max_tif_theta,
        max_expected_score_diff=max_score_diff,
        max_expected_score_diff_theta=max_score_theta,
        passed=passed,
        flags=flags,
    )
