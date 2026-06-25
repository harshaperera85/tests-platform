"""Weighted minimax, inter-form overlap, and rate-based exposure (shared engine)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.assembly import assemble
from app.schemas.blueprint import (
    Blueprint,
    ExposureTarget,
    TIFTarget,
)


def _bp(target_info, weights=None, length=20, **kw):
    return Blueprint(
        length=length,
        statistical_target=TIFTarget(
            theta_points=[-1.0, 0.0, 1.0],
            target_info=target_info,
            method="minimax",
            weights=weights,
        ),
        **kw,
    )


# --- weighted minimax -------------------------------------------------------
def test_unit_weights_reproduce_unweighted(default_pool) -> None:
    """weights=[1,1,1] must give the identical objective + form as no weights."""
    base = assemble(
        _bp([7, 9, 7]), default_pool, strategy="mip", time_limit_s=5, seed=0
    )
    wt = assemble(
        _bp([7, 9, 7], weights=[1.0, 1.0, 1.0]),
        default_pool,
        strategy="mip",
        time_limit_s=5,
        seed=0,
    )
    assert wt.objective_value == pytest.approx(base.objective_value, abs=1e-9)
    assert wt.forms[0].item_ids == base.forms[0].item_ids


def test_weight_protects_the_critical_point(default_pool) -> None:
    """A peaked target the pool can't fully hit: heavily weighting the center must
    not leave the center miss worse than the unweighted solution (it protects fit)."""
    target = [5.0, 14.0, 5.0]  # center 14 exceeds a 20-item form's reach
    unweighted = assemble(_bp(target), default_pool, strategy="mip", time_limit_s=8)
    weighted = assemble(
        _bp(target, weights=[1.0, 10.0, 1.0]),
        default_pool,
        strategy="mip",
        time_limit_s=8,
    )
    center_miss_unw = abs(unweighted.forms[0].tif_actual[1] - 14.0)
    center_miss_w = abs(weighted.forms[0].tif_actual[1] - 14.0)
    assert center_miss_w <= center_miss_unw + 1e-6


def test_weights_validation() -> None:
    with pytest.raises(ValidationError):
        TIFTarget(theta_points=[0, 1], target_info=[5, 5], weights=[1.0])  # wrong len
    with pytest.raises(ValidationError):
        TIFTarget(theta_points=[0], target_info=[5], weights=[0.0])  # non-positive


# --- inter-form pairwise overlap -------------------------------------------
def test_pairwise_overlap_caps_shared_items(default_pool) -> None:
    bp = Blueprint(
        length=15,
        num_forms=3,
        statistical_target=TIFTarget(
            theta_points=[-1, 0, 1], target_info=[5, 6, 5], method="minimax"
        ),
        exposure_target=ExposureTarget(max_pairwise_overlap=3),
    )
    r = assemble(bp, default_pool, strategy="mip", time_limit_s=10)
    assert r.feasible and len(r.forms) == 3
    sets = [set(f.item_ids) for f in r.forms]
    for a in range(3):
        for b in range(a + 1, 3):
            assert len(sets[a] & sets[b]) <= 3


def test_pairwise_overlap_zero_forces_disjoint(default_pool) -> None:
    bp = Blueprint(
        length=15,
        num_forms=2,
        statistical_target=TIFTarget(
            theta_points=[0], target_info=[5], method="minimax"
        ),
        exposure_target=ExposureTarget(max_pairwise_overlap=0),
    )
    r = assemble(bp, default_pool, strategy="mip", time_limit_s=8)
    assert r.feasible
    assert set(r.forms[0].item_ids).isdisjoint(set(r.forms[1].item_ids))


# --- rate-based exposure ----------------------------------------------------
def test_rate_translates_to_max_use() -> None:
    assert ExposureTarget(max_exposure_rate=0.5).resolved_max_use(3) == 2  # ceil(1.5)
    assert ExposureTarget(max_exposure_rate=0.34).resolved_max_use(10) == 4  # ceil(3.4)
    # raw override wins when both are given
    et = ExposureTarget(max_use_per_item=1, max_exposure_rate=0.9)
    assert et.resolved_max_use(10) == 1


def test_rate_exposure_caps_usage(default_pool) -> None:
    from collections import Counter

    bp = Blueprint(
        length=15,
        num_forms=4,
        statistical_target=TIFTarget(
            theta_points=[-1, 0, 1], target_info=[4, 5, 4], method="minimax"
        ),
        exposure_target=ExposureTarget(max_exposure_rate=0.5),  # ceil(0.5*4)=2
    )
    r = assemble(bp, default_pool, strategy="mip", time_limit_s=12)
    assert r.feasible and len(r.forms) == 4
    uses = Counter(i for f in r.forms for i in f.item_ids)
    assert max(uses.values()) <= 2


def test_exposure_target_requires_a_field() -> None:
    with pytest.raises(ValidationError):
        ExposureTarget()
