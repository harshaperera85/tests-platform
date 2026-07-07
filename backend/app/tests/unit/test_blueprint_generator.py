"""Curriculum→blueprint generator (BP-MODES-1 §6).

Runs against the real pre-algebra unit JSON fixtures (`app/data/curriculum/
pre_algebra/`, item-factory export slimmed to the consumed fields): manifest
derivation, exact expected shares (EOC + unit quiz), rounding properties, the pinned
cognitive-dimension contract, binding rules, and the feasibility gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.assembly import assemble
from app.psychometrics.bank import load_default_pool
from app.schemas.blueprint import TIFTarget
from app.schemas.generator import (
    CognitiveProfile,
    CurriculumManifest,
    CurriculumUnit,
    GenerateBlueprintRequest,
    ManifestKC,
    ManifestUnit,
    PerUnitCognitiveMinimum,
)
from app.services.blueprint_generator import (
    check_feasibility,
    generate_blueprint,
    largest_remainder,
    normalize_unit_documents,
)

FIXTURES = Path(__file__).parents[2] / "data" / "curriculum" / "pre_algebra"


def _raw_units() -> list[CurriculumUnit]:
    return [
        CurriculumUnit.model_validate(json.loads(p.read_text()))
        for p in sorted(FIXTURES.glob("unit-*.json"))
    ]


@pytest.fixture(scope="module")
def pre_algebra() -> CurriculumManifest:
    return normalize_unit_documents(_raw_units())


def _synthetic_manifest() -> CurriculumManifest:
    """KC ids chosen to match the demo pool's KC tag values (for assembly e2e)."""
    return CurriculumManifest(
        course_id="course-1",
        course_name="Demo Course",
        units=[
            ManifestUnit(
                unit_id="u1",
                order=1,
                name="Unit One",
                kcs=[
                    ManifestKC(kc_id="algebra", order=1, n_complicators=3),
                    ManifestKC(kc_id="number", order=2, n_complicators=2),
                ],
            )
        ],
    )


# ---------------------------------------------------------- largest remainder
def test_largest_remainder_sums_and_proportionality() -> None:
    assert largest_remainder([7, 3], 20) == [14, 6]
    assert largest_remainder([5, 3, 2], 4) == [2, 1, 1]
    assert largest_remainder([1, 1], 3) == [2, 1]  # deterministic tie-break


def test_largest_remainder_rejects_bad_input() -> None:
    for bad in ([], [0, 0], [1, -1]):
        with pytest.raises(ValueError):
            largest_remainder(bad, 5)


# ---------------------------------------------------- manifest normalization
def test_manifest_derivation_from_raw_unit_json() -> None:
    raw = json.loads((FIXTURES / "unit-09-exponents.json").read_text())
    manifest = normalize_unit_documents([CurriculumUnit.model_validate(raw)])
    assert manifest.course_id == raw["course_id"]
    unit = manifest.units[0]
    assert unit.unit_id == raw["unit_id"]  # identifier carried verbatim
    assert unit.name == "Exponents" and unit.order == 9
    assert [kc.n_complicators for kc in unit.kcs] == [5, 3, 3, 3, 5]
    # kc ids are the export's ids, untouched
    assert [kc.kc_id for kc in unit.kcs] == [
        k["id"] for k in raw["knowledge_components"]
    ]


def test_manifest_full_course(pre_algebra: CurriculumManifest) -> None:
    assert len(pre_algebra.units) == 11
    assert [u.order for u in pre_algebra.units] == list(range(1, 12))
    assert sum(len(u.kcs) for u in pre_algebra.units) == 60
    assert (
        sum(kc.n_complicators for u in pre_algebra.units for kc in u.kcs) == 199
    )


def test_manifest_rejects_mixed_courses_and_duplicates() -> None:
    units = _raw_units()[:2]
    other = units[1].model_copy(update={"course_id": "another-course"})
    with pytest.raises(ValueError, match="several course_ids"):
        normalize_unit_documents([units[0], other])
    with pytest.raises(ValueError, match="duplicate unit_id"):
        normalize_unit_documents([units[0], units[0]])


# --------------------------------------------------------------- EOC recipe
def test_eoc_exact_shares_pre_algebra(pre_algebra: CurriculumManifest) -> None:
    req = GenerateBlueprintRequest(
        manifest=pre_algebra, grain="eoc", length=60, unit_tag="unit"
    )
    bp, shares, _ = generate_blueprint(req, pre_algebra)
    # weights = KCs + complicators per unit; largest-remainder over length 60
    assert [s.weight for s in shares] == [25, 23, 40, 15, 25, 27, 26, 18, 24, 22, 14]
    assert [s.count for s in shares] == [6, 5, 9, 4, 6, 6, 6, 4, 6, 5, 3]
    assert sum(s.count for s in shares) == 60
    # emitted as exact count cells (§2), keyed on the verbatim unit ids
    for c, s in zip(bp.content_constraints, shares, strict=True):
        assert c.mode == "count" and c.tag_type == "unit" and c.tag_value == s.key
        assert c.minimum == s.count and c.maximum == s.count
    assert bp.schema_version == 2
    assert bp.statistical_target is None  # content-only by default
    assert bp.name == "Pre-Algebra New — EOC"


# --------------------------------------------------------------- quiz recipe
def test_unit_quiz_exact_shares(pre_algebra: CurriculumManifest) -> None:
    exponents = next(u for u in pre_algebra.units if u.name == "Exponents")
    req = GenerateBlueprintRequest(
        manifest=pre_algebra, grain="unit_quiz", unit_id=exponents.unit_id, length=12
    )
    bp, shares, _ = generate_blueprint(req, pre_algebra)
    # KC weights 1+complicators = [6,4,4,4,6]; exact quotas at length 12
    assert [s.weight for s in shares] == [6, 4, 4, 4, 6]
    assert [s.count for s in shares] == [3, 2, 2, 2, 3]
    assert [c.tag_type for c in bp.content_constraints] == ["kc"] * 5
    assert bp.name == "Exponents — quiz"


def test_unit_quiz_resolution_errors(pre_algebra: CurriculumManifest) -> None:
    with pytest.raises(ValueError, match="needs unit_id"):
        generate_blueprint(
            GenerateBlueprintRequest(
                manifest=pre_algebra, grain="unit_quiz", length=10
            ),
            pre_algebra,
        )
    with pytest.raises(ValueError, match="not found"):
        generate_blueprint(
            GenerateBlueprintRequest(
                manifest=pre_algebra, grain="unit_quiz", unit_id="nope", length=10
            ),
            pre_algebra,
        )


def test_rounding_sums_to_length(pre_algebra: CurriculumManifest) -> None:
    for length in (10, 20, 37, 60, 101):
        _, shares, _ = generate_blueprint(
            GenerateBlueprintRequest(manifest=pre_algebra, grain="eoc", length=length),
            pre_algebra,
        )
        assert sum(s.count for s in shares) == length


# --------------------------------------------------------- cognitive profile
def test_unknown_cognitive_dimensions_rejected() -> None:
    for dim in ("dok", "bloom", "cognition"):
        with pytest.raises(ValidationError):
            CognitiveProfile(dimension=dim, distribution={"x": 1.0})  # type: ignore[arg-type]


def test_cognitive_value_and_sum_validation() -> None:
    with pytest.raises(ValidationError, match="unknown timss value"):
        CognitiveProfile(
            dimension="timss", distribution={"Knowing": 0.5, "Guessing": 0.5}
        )
    with pytest.raises(ValidationError, match="sum to 1"):
        CognitiveProfile(dimension="timss", distribution={"Knowing": 0.5})
    with pytest.raises(ValidationError, match="distribution and/or"):
        CognitiveProfile(dimension="timss")


def test_cognitive_profile_emission(pre_algebra: CurriculumManifest) -> None:
    u1 = pre_algebra.units[0]
    req = GenerateBlueprintRequest(
        manifest=pre_algebra,
        grain="eoc",
        length=20,
        cognitive_profile=CognitiveProfile(
            dimension="timss",
            distribution={"Knowing": 0.5, "Applying": 0.3, "Reasoning": 0.2},
            per_unit_minimums=[
                PerUnitCognitiveMinimum(
                    unit_id=u1.unit_id, value="Reasoning", minimum=2
                )
            ],
        ),
    )
    bp, _, _ = generate_blueprint(req, pre_algebra)
    cog = bp.content_constraints[11:]  # after the 11 unit cells
    # marginal proportions resolve to the largest-remainder counts: 10/6/4 of 20
    marginals = cog[:3]
    assert [c.tag_type for c in marginals] == ["timss"] * 3
    assert [c.mode for c in marginals] == ["proportion"] * 3
    assert [c.resolved_minimum(bp.length) for c in marginals] == [10, 6, 4]
    assert [c.resolved_maximum(bp.length) for c in marginals] == [10, 6, 4]
    # cross-classified cell: {unit × timss} count minimum
    cell = cog[3]
    assert cell.predicates == {"unit": u1.unit_id, "timss": "Reasoning"}
    assert cell.mode == "count" and cell.minimum == 2 and cell.maximum is None


def test_cognitive_per_unit_minimum_unknown_unit(
    pre_algebra: CurriculumManifest,
) -> None:
    req = GenerateBlueprintRequest(
        manifest=pre_algebra,
        grain="eoc",
        length=20,
        cognitive_profile=CognitiveProfile(
            dimension="timss",
            per_unit_minimums=[
                PerUnitCognitiveMinimum(unit_id="ghost", value="Knowing", minimum=1)
            ],
        ),
    )
    with pytest.raises(ValueError, match="unknown unit_id"):
        generate_blueprint(req, pre_algebra)


# ------------------------------------------------------------ binding rules
def _target(tol: float | None = None) -> TIFTarget:
    return TIFTarget(theta_points=[0.0], target_info=[5.0], tolerance=tol)


def test_binding_rules(pre_algebra: CurriculumManifest) -> None:
    base = dict(manifest=pre_algebra, grain="eoc", length=20)
    # content-only fixed-form is the default — no warning noise
    bp, _, warnings = generate_blueprint(
        GenerateBlueprintRequest(**base), pre_algebra  # type: ignore[arg-type]
    )
    assert bp.statistical_target is None and warnings == []
    # CAT: a supplied target is dropped with the §2.1 warning
    bp, _, warnings = generate_blueprint(
        GenerateBlueprintRequest(  # type: ignore[arg-type]
            **base, binding="cat", statistical_target=_target()
        ),
        pre_algebra,
    )
    assert bp.statistical_target is None
    assert any("will not be enforced" in w for w in warnings)
    # LOFT: target without tolerance rejected (§4.1); content-only warns (§2.1(2))
    with pytest.raises(ValueError, match="tolerance"):
        generate_blueprint(
            GenerateBlueprintRequest(  # type: ignore[arg-type]
                **base, binding="loft", statistical_target=_target()
            ),
            pre_algebra,
        )
    bp, _, warnings = generate_blueprint(
        GenerateBlueprintRequest(**base, binding="loft"),  # type: ignore[arg-type]
        pre_algebra,
    )
    assert any("content only" in w for w in warnings)
    # fixed-form with a target: attached verbatim
    bp, _, warnings = generate_blueprint(
        GenerateBlueprintRequest(  # type: ignore[arg-type]
            **base, statistical_target=_target(tol=0.5)
        ),
        pre_algebra,
    )
    assert bp.statistical_target is not None and warnings == []


# ------------------------------------------------- feasibility gate + assembly
def test_feasibility_gate_and_assembly_e2e() -> None:
    pool = load_default_pool()  # KC: algebra/geometry/number/data, 12 each
    manifest = _synthetic_manifest()
    req = GenerateBlueprintRequest(
        manifest=manifest, grain="unit_quiz", length=10, kc_tag="KC"
    )
    bp, shares, _ = generate_blueprint(req, manifest)
    ok, issues, _ = check_feasibility(bp, pool)
    assert ok and not issues

    result = assemble(bp, pool, strategy="mip", time_limit_s=5)
    assert result.feasible
    form_tags = [pool.get(i).tags["KC"] for i in result.forms[0].item_ids]
    for s in shares:  # the form honors the largest-remainder allocation exactly
        assert form_tags.count(s.key) == s.count

    # over-ask: at length 30 the algebra share resolves to 18 > 12 available
    bp_big, _, _ = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=manifest, grain="unit_quiz", length=30, kc_tag="KC"
        ),
        manifest,
    )
    ok, issues, _ = check_feasibility(bp_big, pool)
    assert not ok and any(i.available == 12 and i.required > 12 for i in issues)
