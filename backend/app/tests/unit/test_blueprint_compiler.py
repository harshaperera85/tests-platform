"""Unit tests for the blueprint compiler (translation, not solving)."""

from __future__ import annotations

from app.assembly.blueprint_compiler import compile_blueprint
from app.schemas.blueprint import (
    Blueprint,
    ContentConstraint,
    EnemyPolicy,
    TIFTarget,
)


def test_compiles_info_matrix_and_targets(default_pool) -> None:
    bp = Blueprint(
        length=10,
        statistical_target=TIFTarget(
            theta_points=[-1.0, 0.0, 1.0], target_info=[5.0, 7.0, 5.0]
        ),
    )
    prob = compile_blueprint(bp, default_pool)
    assert prob.n_items == len(default_pool)
    assert len(prob.info) == len(default_pool)
    assert all(len(row) == 3 for row in prob.info)
    assert prob.target_info == (5.0, 7.0, 5.0)
    assert prob.length == 10


def test_content_constraints_resolve_to_member_indices(default_pool) -> None:
    bp = Blueprint(
        length=10,
        statistical_target=TIFTarget(theta_points=[0.0], target_info=[5.0]),
        content_constraints=[
            ContentConstraint(tag_type="KC", tag_value="algebra", minimum=3, maximum=6)
        ],
    )
    prob = compile_blueprint(bp, default_pool)
    cs = prob.content_sets[0]
    assert cs.minimum == 3 and cs.maximum == 6
    assert all(default_pool.items[i].tags["KC"] == "algebra" for i in cs.members)
    assert len(cs.members) == sum(
        1 for it in default_pool.items if it.tags["KC"] == "algebra"
    )


def test_enemy_relations_are_symmetrized(default_pool) -> None:
    # Fixture declares I011 -> I012 one-directionally; compiler must symmetrize.
    bp = Blueprint(
        length=10, statistical_target=TIFTarget(theta_points=[0.0], target_info=[5.0])
    )
    prob = compile_blueprint(bp, default_pool)
    idx = {iid: i for i, iid in enumerate(prob.item_ids)}
    pair = (min(idx["I011"], idx["I012"]), max(idx["I011"], idx["I012"]))
    assert pair in prob.enemy_pairs


def test_enemy_policy_disabled_drops_pairs(default_pool) -> None:
    bp = Blueprint(
        length=10,
        statistical_target=TIFTarget(theta_points=[0.0], target_info=[5.0]),
        enemy_policy=EnemyPolicy(enforce=False),
    )
    prob = compile_blueprint(bp, default_pool)
    assert prob.enemy_pairs == ()


def test_unmatched_content_minimum_warns(default_pool) -> None:
    bp = Blueprint(
        length=10,
        statistical_target=TIFTarget(theta_points=[0.0], target_info=[5.0]),
        content_constraints=[
            ContentConstraint(tag_type="KC", tag_value="nonexistent", minimum=2)
        ],
    )
    prob = compile_blueprint(bp, default_pool)
    assert any("nonexistent" in w for w in prob.warnings)
