"""G4 — TCC (expected-score) target: hard assembly-time band alongside TIF.

TCC(θ) = Σ Pᵢ(θ) is linear in the selection, so the band rides the same
CP-SAT machinery as information; absent target ⇒ the model is unchanged.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.assembly import assemble
from app.assembly.blueprint_compiler import compile_blueprint
from app.assembly.loft import (
    PoolFormRef,
    assemble_loft_session,
)
from app.psychometrics.information import prob_correct
from app.schemas.blueprint import Blueprint, TCCTarget, TIFTarget

_THETAS = [-1.0, 0.0, 1.0]


def _tcc_of(pool, item_ids: list[str], thetas=None) -> list[float]:
    by_id = {it.item_id: it for it in pool.items}
    return [
        sum(prob_correct(by_id[iid], t) for iid in item_ids)
        for t in (thetas or _THETAS)
    ]


def _bp(tcc: TCCTarget | None = None, tif: bool = True, **kw) -> Blueprint:
    return Blueprint(
        name="tcc-demo",
        length=20,
        statistical_target=(
            TIFTarget(
                theta_points=_THETAS, target_info=[5.0, 6.5, 5.0], tolerance=2.5
            )
            if tif
            else None
        ),
        tcc_target=tcc,
        **kw,
    )


def _feasible_tcc(default_pool, tolerance: float = 0.75) -> TCCTarget:
    """A TCC band centered on a realizable form's expected score."""
    baseline = assemble(
        _bp(), default_pool, strategy="mip", time_limit_s=5, seed=0
    )
    scores = _tcc_of(default_pool, list(baseline.forms[0].item_ids))
    return TCCTarget(
        theta_points=_THETAS,
        target_scores=[round(s, 2) for s in scores],
        tolerance=tolerance,
    )


# ------------------------------------------------------------------- schema
def test_schema_requires_tolerance_and_matching_lengths() -> None:
    with pytest.raises(ValidationError):
        TCCTarget(theta_points=[0.0], target_scores=[8.0])  # no tolerance
    with pytest.raises(ValidationError):
        TCCTarget(theta_points=[0.0, 1.0], target_scores=[8.0], tolerance=1.0)
    with pytest.raises(ValidationError, match="exceeds form length"):
        _bp(TCCTarget(theta_points=[0.0], target_scores=[25.0], tolerance=1.0))


def test_compiler_exposes_tcc_fields(default_pool) -> None:
    tcc = TCCTarget(theta_points=[0.0], target_scores=[10.0], tolerance=1.0)
    p = compile_blueprint(_bp(tcc), default_pool)
    assert p.tcc_theta_points == (0.0,)
    assert p.tcc_target == (10.0,)
    assert p.tcc_tolerance == 1.0
    assert len(p.prob) == p.n_items and len(p.prob[0]) == 1
    assert all(0.0 <= p.prob[i][0] <= 1.0 for i in range(p.n_items))
    # no target -> no TCC machinery at all
    p0 = compile_blueprint(_bp(), default_pool)
    assert p0.prob == () and p0.tcc_target == () and p0.tcc_tolerance is None


# ------------------------------------------------------------ mip hard band
def test_mip_honors_the_tcc_band(default_pool) -> None:
    tcc = _feasible_tcc(default_pool)
    result = assemble(
        _bp(tcc), default_pool, strategy="mip", time_limit_s=10, seed=3
    )
    assert result.feasible
    realized = _tcc_of(default_pool, list(result.forms[0].item_ids))
    for actual, target in zip(realized, tcc.target_scores, strict=True):
        assert abs(actual - target) <= tcc.tolerance + 1e-6


def test_mip_tcc_band_without_tif_target(default_pool) -> None:
    """Score-parallel-only blueprint: TCC band with no TIF objective."""
    tcc = _feasible_tcc(default_pool, tolerance=1.0)
    result = assemble(
        _bp(tcc, tif=False), default_pool, strategy="mip", time_limit_s=10, seed=1
    )
    assert result.feasible
    realized = _tcc_of(default_pool, list(result.forms[0].item_ids))
    for actual, target in zip(realized, tcc.target_scores, strict=True):
        assert abs(actual - target) <= tcc.tolerance + 1e-6


def test_impossible_tcc_band_is_infeasible(default_pool) -> None:
    tcc = TCCTarget(  # expected score = length requires P=1 everywhere
        theta_points=[-1.0], target_scores=[20.0], tolerance=0.05
    )
    result = assemble(
        _bp(tcc), default_pool, strategy="mip", time_limit_s=10, seed=0
    )
    assert not result.feasible


def test_absent_tcc_target_leaves_assembly_unchanged(default_pool) -> None:
    """No tcc_target ⇒ identical model ⇒ identical solution (same seed)."""
    a = assemble(_bp(), default_pool, strategy="mip", time_limit_s=5, seed=7,
                 num_workers=1)
    b = assemble(_bp(), default_pool, strategy="mip", time_limit_s=5, seed=7,
                 num_workers=1)
    assert a.forms[0].item_ids == b.forms[0].item_ids


# --------------------------------------------------------------- LOFT (§4)
def test_loft_engines_honor_the_tcc_band(default_pool) -> None:
    tcc = _feasible_tcc(default_pool, tolerance=1.25)
    bp = _bp(tcc)
    for engine in ("random_constrained", "cp_sat"):
        for seed in range(3):
            form = assemble_loft_session(
                bp, default_pool, engine=engine, seed=seed
            )
            for actual, target in zip(
                form.record["tcc_actual"], tcc.target_scores, strict=True
            ):
                assert abs(actual - target) <= tcc.tolerance + 1e-6, (engine, seed)
            assert form.record["tcc_tolerance"] == tcc.tolerance


def test_loft_pregenerated_rechecks_the_tcc_band(default_pool) -> None:
    tcc = _feasible_tcc(default_pool, tolerance=0.75)
    bp = _bp(tcc)
    good = tuple(
        assemble_loft_session(bp, default_pool, engine="cp_sat", seed=1).item_ids
    )
    # a form conforming in content+TIF but assembled blind to the TCC band
    blind = tuple(
        assemble_loft_session(_bp(), default_pool, engine="cp_sat", seed=99).item_ids
    )
    pool_forms = [
        PoolFormRef(form_id="blind", item_ids=blind),
        PoolFormRef(form_id="good", item_ids=good),
    ]
    form = assemble_loft_session(
        bp, default_pool, engine="pregenerated", seed=2, form_pool=pool_forms
    )
    assert form.record["form_id"] == "good"
    if form.record["n_nonconforming"]:
        assert any("TCC" in w for w in form.warnings)


def test_loft_tcc_without_tif_warns_score_parallel(default_pool) -> None:
    tcc = _feasible_tcc(default_pool, tolerance=1.5)
    form = assemble_loft_session(_bp(tcc, tif=False), default_pool, seed=4)
    assert any("score-parallel" in w for w in form.warnings)
    assert not any("content only" in w for w in form.warnings)
