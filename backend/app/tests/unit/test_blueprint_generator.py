"""Curriculum→blueprint generator (BP-MODES-1 §6): recipes, rounding, bindings, gate.

The curriculum fixtures mirror the verified item-factory unit JSON shape (one document
per unit: course_id/unit_id/unit_name/knowledge_components[{id, order, name,
complicators}]); KC ids are chosen to match the demo pool's KC tag values so the
feasibility gate can be exercised for real.
"""

from __future__ import annotations

import pytest

from app.assembly import assemble, compile_blueprint
from app.psychometrics.bank import load_default_pool
from app.schemas.blueprint import ContentConstraint, TIFTarget
from app.schemas.generator import CurriculumUnit, GenerateBlueprintRequest
from app.services.blueprint_generator import (
    check_feasibility,
    generate_blueprint,
    largest_remainder,
)


def _comps(n: int, prefix: str) -> list[dict]:
    return [{"id": f"{prefix}-c{i}", "order": i, "name": f"comp {i}"} for i in range(n)]


def _unit(unit_id: str, kcs: list[tuple[str, int]], order: int = 1) -> CurriculumUnit:
    """A unit document shaped exactly like the item-factory export."""
    return CurriculumUnit.model_validate(
        {
            "course_id": "course-1",
            "course_name": "Demo Course",
            "unit_id": unit_id,
            "unit_order": order,
            "unit_name": unit_id.title(),
            "knowledge_components": [
                {"id": kc_id, "order": i + 1, "name": f"KC {kc_id}",
                 "complicators": _comps(n, kc_id)}
                for i, (kc_id, n) in enumerate(kcs)
            ],
        }
    )


# unit "alg": 2 KCs + 5 complicators = weight 7; unit "geo": 1 KC + 2 = weight 3
ALG = _unit("alg", [("algebra", 3), ("number", 2)], order=1)
GEO = _unit("geo", [("geometry", 2)], order=2)


# ---------------------------------------------------------- largest remainder
def test_largest_remainder_sums_and_proportionality() -> None:
    assert largest_remainder([7, 3], 20) == [14, 6]
    assert sum(largest_remainder([3, 3, 1], 10)) == 10
    # remainder goes to the largest fractional part: 10*[.5,.3,.2] over 4 -> 2,1,1
    assert largest_remainder([5, 3, 2], 4) == [2, 1, 1]


def test_largest_remainder_tie_breaks_deterministic() -> None:
    # equal weights, total not divisible: earlier index wins the remainder
    assert largest_remainder([1, 1], 3) == [2, 1]
    assert largest_remainder([1, 1, 1], 4) == [2, 1, 1]


def test_largest_remainder_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        largest_remainder([], 5)
    with pytest.raises(ValueError):
        largest_remainder([0, 0], 5)
    with pytest.raises(ValueError):
        largest_remainder([1, -1], 5)


# ------------------------------------------------------------- course grain
def test_course_grain_unit_shares() -> None:
    req = GenerateBlueprintRequest(
        units=[ALG, GEO], grain="course", length=20, unit_tag="unit"
    )
    bp, shares, _ = generate_blueprint(req)
    # weights 7 and 3 -> 14 and 6 of 20
    assert [(s.key, s.weight, s.count) for s in shares] == [
        ("alg", 7, 14),
        ("geo", 3, 6),
    ]
    assert sum(s.count for s in shares) == req.length
    # proportion constraints resolve back to exactly the rounded counts
    assert [c.tag_type for c in bp.content_constraints] == ["unit", "unit"]
    assert [c.resolved_minimum(bp.length) for c in bp.content_constraints] == [14, 6]
    assert [c.resolved_maximum(bp.length) for c in bp.content_constraints] == [14, 6]
    assert bp.name == "Demo Course — EOC"


# --------------------------------------------------------------- unit grain
def test_unit_grain_kc_shares() -> None:
    req = GenerateBlueprintRequest(
        units=[ALG], grain="unit", length=10, kc_tag="KC"
    )
    bp, shares, _ = generate_blueprint(req)
    # KC weights 1+3=4 and 1+2=3 -> 6 and 4 of 10 (largest remainder)
    assert [(s.key, s.weight, s.count) for s in shares] == [
        ("algebra", 4, 6),
        ("number", 3, 4),
    ]
    assert [c.tag_type for c in bp.content_constraints] == ["KC", "KC"]
    assert bp.name == "Alg — quiz"


def test_unit_grain_resolution_errors() -> None:
    with pytest.raises(ValueError, match="needs unit_id"):
        generate_blueprint(
            GenerateBlueprintRequest(units=[ALG, GEO], grain="unit", length=10)
        )
    with pytest.raises(ValueError, match="not found"):
        generate_blueprint(
            GenerateBlueprintRequest(
                units=[ALG], grain="unit", unit_id="nope", length=10
            )
        )


# ------------------------------------------------------------ binding rules
def _target(tol: float | None = None) -> TIFTarget:
    return TIFTarget(theta_points=[0.0], target_info=[5.0], tolerance=tol)


def test_cat_binding_drops_target_with_warning() -> None:
    bp, _, warnings = generate_blueprint(
        GenerateBlueprintRequest(
            units=[ALG], grain="unit", length=10, binding="cat",
            statistical_target=_target(),
        )
    )
    assert bp.statistical_target is None
    assert any("will not be enforced" in w for w in warnings)


def test_loft_binding_requires_tolerance() -> None:
    with pytest.raises(ValueError, match="tolerance"):
        generate_blueprint(
            GenerateBlueprintRequest(
                units=[ALG], grain="unit", length=10, binding="loft",
                statistical_target=_target(tol=None),
            )
        )
    bp, _, warnings = generate_blueprint(
        GenerateBlueprintRequest(
            units=[ALG], grain="unit", length=10, binding="loft",
            statistical_target=_target(tol=0.5),
        )
    )
    assert bp.statistical_target is not None
    assert not warnings


def test_content_only_bindings_warn() -> None:
    cases = (("fixed_form", "feasibility-only"), ("loft", "content only"))
    for binding, needle in cases:
        _, _, warnings = generate_blueprint(
            GenerateBlueprintRequest(
                units=[ALG], grain="unit", length=10, binding=binding  # type: ignore[arg-type]
            )
        )
        assert any(needle in w for w in warnings), (binding, warnings)


def test_cognitive_minimums_pass_through() -> None:
    extra = ContentConstraint(tag_type="Bloom", tag_value="analyze", minimum=3)
    bp, _, _ = generate_blueprint(
        GenerateBlueprintRequest(
            units=[ALG], grain="unit", length=10, cognitive_minimums=[extra]
        )
    )
    assert bp.content_constraints[-1] == extra


# ------------------------------------------------- feasibility gate + assembly
def test_feasibility_gate_against_pool() -> None:
    pool = load_default_pool()  # KC: algebra/geometry/number/data, 12 each
    bp, _, _ = generate_blueprint(
        GenerateBlueprintRequest(units=[ALG], grain="unit", length=10, kc_tag="KC")
    )
    ok, issues, _ = check_feasibility(bp, pool)
    assert ok and not issues

    # over-ask: at length 30 the algebra share resolves to 18 > 12 available
    bp_big, _, _ = generate_blueprint(
        GenerateBlueprintRequest(units=[ALG], grain="unit", length=30, kc_tag="KC")
    )
    ok, issues, _ = check_feasibility(bp_big, pool)
    assert not ok
    assert any(i.available == 12 and i.required > 12 for i in issues)

    # unknown tag values -> nothing matches
    bp_alien, _, _ = generate_blueprint(
        GenerateBlueprintRequest(units=[GEO], grain="course", length=10)
    )  # unit_tag 'unit' with value 'geo' does not exist in the demo pool
    ok, issues, _ = check_feasibility(bp_alien, pool)
    assert not ok and issues[0].available == 0


def test_generated_blueprint_compiles_and_assembles() -> None:
    pool = load_default_pool()
    bp, shares, _ = generate_blueprint(
        GenerateBlueprintRequest(units=[ALG], grain="unit", length=10, kc_tag="KC")
    )
    problem = compile_blueprint(bp, pool)
    assert problem.feasibility_only is True  # content-only by default
    result = assemble(bp, pool, strategy="mip", time_limit_s=5)
    assert result.feasible
    # the assembled form honors the largest-remainder allocation exactly
    form_tags = [pool.get(i).tags["KC"] for i in result.forms[0].item_ids]
    for s in shares:
        assert form_tags.count(s.key) == s.count
