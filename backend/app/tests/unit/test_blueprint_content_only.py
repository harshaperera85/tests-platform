"""BP-MODES-1 §2 amendments: content-only blueprints, versioning, reserved fields.

Covers the schema relaxations (A1 optional ``statistical_target``, §8
``schema_version``, A4 reserved ``segments``) and the fixed-form consequence: a
content-only blueprint assembles for feasibility only (no TIF objective) while still
reporting realized TIF. Targeted (TIF-bearing) assembly is asserted unchanged.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.assembly import assemble, compile_blueprint
from app.schemas.blueprint import (
    Blueprint,
    ContentConstraint,
    TIFTarget,
)


def _content_only() -> Blueprint:
    """A satisfiable content-only blueprint over the fixture pool (no TIF target)."""
    return Blueprint(
        name="content-only",
        length=20,
        content_constraints=[
            ContentConstraint(tag_type="KC", tag_value="algebra", minimum=4, maximum=8),
            ContentConstraint(tag_type="KC", tag_value="geometry", minimum=4),
        ],
    )


# --------------------------------------------------------------- A1: optional target
def test_content_only_blueprint_accepted() -> None:
    bp = _content_only()
    assert bp.statistical_target is None
    assert bp.schema_version == 2


def test_content_only_compiles_feasibility_only() -> None:
    from app.psychometrics.bank import load_default_pool

    problem = compile_blueprint(_content_only(), load_default_pool())
    assert problem.feasibility_only is True
    assert problem.method == "none"
    assert problem.target_info == ()          # no target curve
    assert problem.theta_points                # reporting grid is populated
    assert problem.tolerance is None
    assert problem.weights == ()


@pytest.mark.parametrize("strategy", ["mip", "random_constrained"])
def test_content_only_assembles_and_reports_tif(default_pool, strategy: str) -> None:
    bp = _content_only()
    result = assemble(bp, default_pool, strategy=strategy, time_limit_s=5)

    assert result.feasible
    form = result.forms[0]
    assert len(form.item_ids) == bp.length
    # content constraints are still enforced under feasibility-only assembly
    from collections import Counter

    kc = Counter(default_pool.get(i).tags["KC"] for i in form.item_ids)
    assert 4 <= kc["algebra"] <= 8
    assert kc["geometry"] >= 4
    # realized TIF IS reported (over the reporting grid), but there is no objective
    # value and no target curve to miss.
    assert result.objective_value is None
    assert result.target_info == []
    assert len(form.tif_actual) == len(result.theta_points) > 0
    assert all(v >= 0.0 for v in form.tif_actual)
    assert sum(form.tif_actual) > 0.0


# ------------------------------------------------------------------- §8: versioning
def test_v1_document_without_schema_version_still_validates() -> None:
    # A stored v1 document: no schema_version key, TIF target present.
    v1 = {
        "name": "legacy-v1",
        "length": 20,
        "statistical_target": {
            "theta_points": [-1.0, 0.0, 1.0],
            "target_info": [7.0, 9.0, 7.0],
            "method": "minimax",
        },
        "content_constraints": [
            {"tag_type": "KC", "tag_value": "algebra", "minimum": 4, "maximum": 8},
        ],
    }
    bp = Blueprint.model_validate(v1)
    assert bp.schema_version == 2  # every v1 document is a valid v2 document
    assert bp.statistical_target is not None
    assert bp.statistical_target.method == "minimax"


# ----------------------------------------------------------- A4: reserved segments
def test_segments_non_none_rejected() -> None:
    with pytest.raises(ValidationError, match="reserved"):
        Blueprint(
            length=20,
            statistical_target=TIFTarget(theta_points=[0.0], target_info=[5.0]),
            segments=[{"delivery_mode": "cat"}],
        )


def test_segments_default_none_accepted() -> None:
    bp = Blueprint(
        length=20,
        statistical_target=TIFTarget(theta_points=[0.0], target_info=[5.0]),
    )
    assert bp.segments is None


# ---------------------------------------------- targeted assembly is UNCHANGED
def test_targeted_assembly_still_optimizes(default_pool, linear_blueprint) -> None:
    result = assemble(linear_blueprint, default_pool, strategy="mip", time_limit_s=5)
    assert result.feasible
    # a TIF-bearing blueprint still carries an objective value and target curve.
    assert result.objective_value is not None
    assert result.target_info == list(linear_blueprint.statistical_target.target_info)
    assert result.method == "minimax"
