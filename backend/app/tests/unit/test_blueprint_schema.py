"""Unit tests for the Blueprint pydantic schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.blueprint import (
    Blueprint,
    ContentConstraint,
    EnemyPolicy,
    TIFTarget,
)


def _target() -> TIFTarget:
    return TIFTarget(theta_points=[0.0], target_info=[5.0])


def test_content_constraint_requires_a_bound() -> None:
    with pytest.raises(ValidationError):
        ContentConstraint(tag_type="KC", tag_value="algebra")


def test_content_constraint_min_gt_max_rejected() -> None:
    with pytest.raises(ValidationError):
        ContentConstraint(tag_type="KC", tag_value="algebra", minimum=5, maximum=2)


def test_tif_target_length_mismatch_rejected() -> None:
    with pytest.raises(ValidationError):
        TIFTarget(theta_points=[-1.0, 1.0], target_info=[5.0])


def test_tif_target_negative_info_rejected() -> None:
    with pytest.raises(ValidationError):
        TIFTarget(theta_points=[0.0], target_info=[-1.0])


def test_blueprint_minimum_exceeding_length_rejected() -> None:
    with pytest.raises(ValidationError):
        Blueprint(
            length=5,
            statistical_target=_target(),
            content_constraints=[
                ContentConstraint(tag_type="KC", tag_value="algebra", minimum=6)
            ],
        )


def test_blueprint_defaults() -> None:
    bp = Blueprint(length=10, statistical_target=_target())
    assert bp.num_forms == 1
    assert bp.enemy_policy == EnemyPolicy(enforce=True)
    assert bp.exposure_target is None
    assert bp.statistical_target.method == "minimax"
