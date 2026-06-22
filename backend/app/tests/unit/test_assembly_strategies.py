"""Unit tests for the assembly strategies (mip, random_constrained) + registry."""

from __future__ import annotations

from collections import Counter

import pytest

from app.assembly import assemble
from app.assembly.strategies import available_strategies, get_assembly_strategy
from app.schemas.blueprint import (
    Blueprint,
    ContentConstraint,
    ExposureTarget,
    TIFTarget,
)


def _counts(pool, item_ids, tag_type):
    return Counter(pool.get(i).tags[tag_type] for i in item_ids)


def test_both_strategies_registered() -> None:
    assert set(available_strategies()) >= {"mip", "random_constrained"}


def test_unknown_strategy_raises() -> None:
    with pytest.raises(KeyError):
        get_assembly_strategy("does-not-exist")


def test_mip_satisfies_all_constraints(default_pool, linear_blueprint) -> None:
    result = assemble(linear_blueprint, default_pool, strategy="mip", time_limit_s=5)
    assert result.feasible
    form = result.forms[0]
    assert len(form.item_ids) == linear_blueprint.length
    kc = _counts(default_pool, form.item_ids, "KC")
    assert 4 <= kc["algebra"] <= 8
    assert kc["geometry"] >= 4
    bloom = _counts(default_pool, form.item_ids, "Bloom")
    assert bloom["analyze"] >= 3
    # enemies respected
    ids = set(form.item_ids)
    assert not ({"I001", "I002"} <= ids)
    assert not ({"I011", "I012"} <= ids)


def test_mip_matches_tif_target_closely(default_pool, linear_blueprint) -> None:
    result = assemble(linear_blueprint, default_pool, strategy="mip", time_limit_s=5)
    # near-exact: the fixture pool can hit this target within a small band.
    assert result.objective_value is not None
    assert result.objective_value < 0.5
    form = result.forms[0]
    for actual, target in zip(form.tif_actual, result.target_info, strict=True):
        assert abs(actual - target) < 0.5


def test_mip_maximin_objective(default_pool) -> None:
    bp = Blueprint(
        length=20,
        statistical_target=TIFTarget(
            theta_points=[-1.0, 0.0, 1.0],
            target_info=[5.0, 5.0, 5.0],
            method="maximin",
        ),
    )
    result = assemble(bp, default_pool, strategy="mip", time_limit_s=5)
    assert result.feasible
    # maximin pushes the worst point's information up to/above the target floor.
    assert min(result.forms[0].tif_actual) >= 5.0


def test_mip_infeasible_when_overconstrained(default_pool) -> None:
    # Demand more 'algebra' items than the pool holds in a single form.
    bp = Blueprint(
        length=20,
        statistical_target=TIFTarget(theta_points=[0.0], target_info=[5.0]),
        content_constraints=[
            ContentConstraint(
                tag_type="KC", tag_value="algebra", minimum=20, maximum=20
            )
        ],
    )
    result = assemble(bp, default_pool, strategy="mip", time_limit_s=5)
    assert result.status == "infeasible"
    assert not result.forms


def test_exposure_caps_overlap_across_forms(default_pool) -> None:
    bp = Blueprint(
        length=15,
        num_forms=2,
        statistical_target=TIFTarget(
            theta_points=[-1.0, 0.0, 1.0], target_info=[5.0, 6.0, 5.0]
        ),
        exposure_target=ExposureTarget(max_use_per_item=1),
    )
    result = assemble(bp, default_pool, strategy="mip", time_limit_s=8)
    assert result.feasible and len(result.forms) == 2
    a, b = set(result.forms[0].item_ids), set(result.forms[1].item_ids)
    assert a.isdisjoint(b)


def test_random_constrained_is_feasible_and_deterministic(
    default_pool, linear_blueprint
) -> None:
    r1 = assemble(linear_blueprint, default_pool, strategy="random_constrained", seed=7)
    r2 = assemble(linear_blueprint, default_pool, strategy="random_constrained", seed=7)
    assert r1.feasible
    assert r1.forms[0].item_ids == r2.forms[0].item_ids  # deterministic by seed
    kc = _counts(default_pool, r1.forms[0].item_ids, "KC")
    assert 4 <= kc["algebra"] <= 8
    assert kc["geometry"] >= 4


def test_mip_beats_random_on_tif(default_pool, linear_blueprint) -> None:
    mip = assemble(linear_blueprint, default_pool, strategy="mip", time_limit_s=5)
    rnd = assemble(
        linear_blueprint, default_pool, strategy="random_constrained", seed=1
    )
    # The optimizing strategy must match the target at least as well.
    assert mip.objective_value <= rnd.objective_value
