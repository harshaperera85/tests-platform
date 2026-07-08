"""Curriculum→blueprint generator (BP-MODES-1 §6, rev. 2026-07-09).

Runs against the real pre-algebra unit JSON fixtures (`app/data/curriculum/
pre_algebra/`): manifest derivation, §6.1 dimension-sum weights with median
imputation (fixtures carry no dimension counts ⇒ fully imputed at 1.0, i.e. the
spec's degenerate case), §6.2 test-type scopes + per-complicator maxima, rounding
properties, the pinned cognitive contract, binding rules, and the feasibility gate.
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
    ManifestComplicator,
    ManifestKC,
    ManifestUnit,
    PerUnitCognitiveMinimum,
)
from app.services.blueprint_generator import (
    check_feasibility,
    generate_blueprint,
    largest_remainder,
    normalize_unit_documents,
    resolve_scope,
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
    assert largest_remainder([2.5, 2.5, 5.0], 4) == [1, 1, 2]  # float weights


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
    assert [len(kc.complicators) for kc in unit.kcs] == [5, 3, 3, 3, 5]
    # complicator ids carried; dimension counts unknown (not in today's export)
    assert all(
        c.id and c.n_dimensions is None for kc in unit.kcs for c in kc.complicators
    )
    assert [kc.kc_id for kc in unit.kcs] == [
        k["id"] for k in raw["knowledge_components"]
    ]


def test_manifest_full_course(pre_algebra: CurriculumManifest) -> None:
    assert len(pre_algebra.units) == 11
    assert [u.order for u in pre_algebra.units] == list(range(1, 12))
    assert sum(len(u.kcs) for u in pre_algebra.units) == 60
    assert (
        sum(len(kc.complicators) for u in pre_algebra.units for kc in u.kcs) == 199
    )


def test_manifest_rejects_mixed_courses_and_duplicates() -> None:
    units = _raw_units()[:2]
    other = units[1].model_copy(update={"course_id": "another-course"})
    with pytest.raises(ValueError, match="several course_ids"):
        normalize_unit_documents([units[0], other])
    with pytest.raises(ValueError, match="duplicate unit_id"):
        normalize_unit_documents([units[0], units[0]])


def test_manifest_kc_count_sugar() -> None:
    kc = ManifestKC(kc_id="x", n_complicators=3)
    assert len(kc.complicators) == 3
    assert all(c.n_dimensions is None for c in kc.complicators)


# --------------------------------------------------- §6.1 dimension weights
def test_fixtures_fully_imputed_degenerate_case(
    pre_algebra: CurriculumManifest,
) -> None:
    """No dimension data ⇒ every complicator imputed at median fallback 1.0 —
    the spec's degenerate case where weights reduce to complicator counts."""
    req = GenerateBlueprintRequest(
        manifest=pre_algebra, test_type="cumulative_final", length=60
    )
    bp, shares, imputed_fraction, warnings = generate_blueprint(req, pre_algebra)
    assert imputed_fraction == 1.0
    assert any("imputed" in w for w in warnings)
    # w(unit) = Σ complicators (all weights 1.0 each)
    assert [s.weight for s in shares] == [19, 18, 32, 11, 19, 20, 20, 13, 19, 17, 11]
    assert [s.count for s in shares] == [6, 5, 10, 3, 6, 6, 6, 4, 6, 5, 3]
    assert sum(s.count for s in shares) == 60


def test_dimension_sums_and_median_imputation() -> None:
    """Known dimension counts drive weights; unknowns get the domain median."""
    m = CurriculumManifest(
        course_id="c",
        units=[
            ManifestUnit(
                unit_id="u1",
                kcs=[
                    ManifestKC(
                        kc_id="k1",
                        complicators=[
                            ManifestComplicator(id="a", n_dimensions=4),
                            ManifestComplicator(id="b", n_dimensions=2),
                        ],
                    ),
                    ManifestKC(
                        kc_id="k2",
                        complicators=[
                            ManifestComplicator(id="c"),  # unknown -> median(4,2)=3
                        ],
                    ),
                ],
            )
        ],
    )
    req = GenerateBlueprintRequest(manifest=m, test_type="unit_quiz", length=9)
    _, shares, imputed_fraction, _ = generate_blueprint(req, m)
    # w(k1) = 4+2 = 6 (known); w(k2) = imputed median 3.0
    assert [s.weight for s in shares] == [6.0, 3.0]
    assert [s.n_imputed for s in shares] == [0, 1]
    assert [s.count for s in shares] == [6, 3]
    assert imputed_fraction == pytest.approx(1 / 3)


# ------------------------------------------------------- §6.2 scopes + types
def test_scope_resolution(pre_algebra: CurriculumManifest) -> None:
    mid = resolve_scope(
        pre_algebra,
        GenerateBlueprintRequest(
            manifest=pre_algebra, test_type="mid_course", length=30
        ),
    )
    eoc = resolve_scope(
        pre_algebra,
        GenerateBlueprintRequest(
            manifest=pre_algebra, test_type="end_of_course", length=30
        ),
    )
    fin = resolve_scope(
        pre_algebra,
        GenerateBlueprintRequest(
            manifest=pre_algebra, test_type="cumulative_final", length=60
        ),
    )
    assert [u.order for u in mid] == [1, 2, 3, 4, 5, 6]  # first half (ceil)
    assert [u.order for u in eoc] == [7, 8, 9, 10, 11]  # the rest
    assert len(fin) == 11


def test_mid_and_eoc_renormalized_shares(pre_algebra: CurriculumManifest) -> None:
    _, mid, _, _ = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=pre_algebra, test_type="mid_course", length=30
        ),
        pre_algebra,
    )
    assert [s.weight for s in mid] == [19, 18, 32, 11, 19, 20]
    assert [s.count for s in mid] == [5, 4, 8, 3, 5, 5]
    _, eoc, _, _ = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=pre_algebra, test_type="end_of_course", length=30
        ),
        pre_algebra,
    )
    assert [s.weight for s in eoc] == [20, 13, 19, 17, 11]
    assert [s.count for s in eoc] == [8, 5, 7, 6, 4]


def test_explicit_scope_override(pre_algebra: CurriculumManifest) -> None:
    two = [pre_algebra.units[0].unit_id, pre_algebra.units[8].unit_id]
    _, shares, _, _ = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=pre_algebra,
            test_type="cumulative_final",
            scope_unit_ids=two,
            length=10,
        ),
        pre_algebra,
    )
    assert [s.key for s in shares] == two  # only the scoped units, in given order
    with pytest.raises(ValueError, match="not in the curriculum"):
        generate_blueprint(
            GenerateBlueprintRequest(
                manifest=pre_algebra,
                test_type="cumulative_final",
                scope_unit_ids=["ghost"],
                length=10,
            ),
            pre_algebra,
        )


def test_unit_quiz_shares_and_complicator_maxima(
    pre_algebra: CurriculumManifest,
) -> None:
    exponents = next(u for u in pre_algebra.units if u.name == "Exponents")
    req = GenerateBlueprintRequest(
        manifest=pre_algebra,
        test_type="unit_quiz",
        unit_id=exponents.unit_id,
        length=12,
    )
    bp, shares, _, _ = generate_blueprint(req, pre_algebra)
    assert [s.weight for s in shares] == [5, 3, 3, 3, 5]
    assert [s.count for s in shares] == [3, 2, 2, 2, 3]
    # per-KC cells are count min=max (LOFT default binding); 19 complicator maxima
    kc_cells = bp.content_constraints[:5]
    assert all(c.mode == "count" and c.minimum == c.maximum for c in kc_cells)
    maxima = [
        c
        for c in bp.content_constraints
        if c.tag_type == "complicator" and c.minimum is None
    ]
    assert len(maxima) == 19
    assert all(c.maximum == 2 and c.mode == "count" for c in maxima)
    assert bp.name == "Exponents — quiz"


def test_unit_quiz_resolution_errors(pre_algebra: CurriculumManifest) -> None:
    with pytest.raises(ValueError, match="needs unit_id"):
        generate_blueprint(
            GenerateBlueprintRequest(
                manifest=pre_algebra, test_type="unit_quiz", length=10
            ),
            pre_algebra,
        )
    with pytest.raises(ValueError, match="not found"):
        generate_blueprint(
            GenerateBlueprintRequest(
                manifest=pre_algebra, test_type="unit_quiz", unit_id="nope", length=10
            ),
            pre_algebra,
        )


def test_rounding_sums_to_length(pre_algebra: CurriculumManifest) -> None:
    for tt, length in (
        ("cumulative_final", 10),
        ("cumulative_final", 37),
        ("mid_course", 21),
        ("end_of_course", 33),
    ):
        _, shares, _, _ = generate_blueprint(
            GenerateBlueprintRequest(
                manifest=pre_algebra, test_type=tt, length=length  # type: ignore[arg-type]
            ),
            pre_algebra,
        )
        assert sum(s.count for s in shares) == length


# ------------------------------------------------- bindings + cell encoding
def _target(tol: float | None = None) -> TIFTarget:
    return TIFTarget(theta_points=[0.0], target_info=[5.0], tolerance=tol)


def test_binding_defaults_per_test_type(pre_algebra: CurriculumManifest) -> None:
    # CAT-shaped types default to proportion cells (content-only)
    bp, _, _, _ = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=pre_algebra, test_type="cumulative_final", length=60
        ),
        pre_algebra,
    )
    assert all(c.mode == "proportion" for c in bp.content_constraints)
    assert bp.statistical_target is None
    # unit quiz defaults to LOFT -> count cells + content-only LOFT notice
    exp = next(u for u in pre_algebra.units if u.name == "Exponents")
    bp, _, _, warnings = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=pre_algebra,
            test_type="unit_quiz",
            unit_id=exp.unit_id,
            length=12,
        ),
        pre_algebra,
    )
    assert bp.content_constraints[0].mode == "count"
    assert any("content only" in w for w in warnings)
    # explicit binding override wins
    bp, _, _, _ = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=pre_algebra,
            test_type="cumulative_final",
            length=60,
            binding="fixed_form",
        ),
        pre_algebra,
    )
    assert all(c.mode == "count" for c in bp.content_constraints)


def test_cat_binding_drops_target_and_scales(pre_algebra: CurriculumManifest) -> None:
    bp, shares, _, warnings = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=pre_algebra,
            test_type="cumulative_final",
            length=60,
            statistical_target=_target(),
        ),
        pre_algebra,
    )
    assert bp.statistical_target is None
    assert any("will not be enforced" in w for w in warnings)
    cells = bp.content_constraints
    # scale-free: proportions recover the counts at the authored length and a
    # sane allocation at a smaller realized length (§3.2)
    assert [c.resolved_minimum(60) for c in cells] == [s.count for s in shares]
    assert sum(c.resolved_minimum(30) or 0 for c in cells) <= 33


def test_loft_binding_requires_tolerance(pre_algebra: CurriculumManifest) -> None:
    exp = next(u for u in pre_algebra.units if u.name == "Exponents")
    with pytest.raises(ValueError, match="tolerance"):
        generate_blueprint(
            GenerateBlueprintRequest(
                manifest=pre_algebra,
                test_type="unit_quiz",
                unit_id=exp.unit_id,
                length=12,
                statistical_target=_target(),
            ),
            pre_algebra,
        )
    bp, _, _, _ = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=pre_algebra,
            test_type="unit_quiz",
            unit_id=exp.unit_id,
            length=12,
            statistical_target=_target(tol=0.5),
        ),
        pre_algebra,
    )
    assert bp.statistical_target is not None


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
        test_type="cumulative_final",
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
    bp, _, _, _ = generate_blueprint(req, pre_algebra)
    cog = bp.content_constraints[11:]  # after the 11 unit cells
    marginals = cog[:3]
    assert [c.tag_type for c in marginals] == ["timss"] * 3
    assert [c.resolved_minimum(bp.length) for c in marginals] == [10, 6, 4]
    cell = cog[3]
    assert cell.predicates == {"unit": u1.unit_id, "timss": "Reasoning"}
    assert cell.mode == "count" and cell.minimum == 2 and cell.maximum is None


def test_cognitive_per_unit_minimum_unknown_unit(
    pre_algebra: CurriculumManifest,
) -> None:
    req = GenerateBlueprintRequest(
        manifest=pre_algebra,
        test_type="cumulative_final",
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


# ------------------------------------------------- feasibility gate + assembly
def test_feasibility_gate_and_assembly_e2e() -> None:
    pool = load_default_pool()  # KC: algebra/geometry/number/data, 12 each
    manifest = _synthetic_manifest()
    req = GenerateBlueprintRequest(
        manifest=manifest,
        test_type="unit_quiz",
        length=10,
        kc_tag="KC",
        binding="fixed_form",  # count cells; demo pool has no complicator tags
    )
    bp, shares, _, _ = generate_blueprint(req, manifest)
    # anonymous complicators (count sugar) -> no maxima cells, only KC cells
    assert all(c.tag_type == "KC" for c in bp.content_constraints)
    ok, issues, _ = check_feasibility(bp, pool)
    assert ok and not issues

    result = assemble(bp, pool, strategy="mip", time_limit_s=5)
    assert result.feasible
    form_tags = [pool.get(i).tags["KC"] for i in result.forms[0].item_ids]
    for s in shares:  # the form honors the largest-remainder allocation exactly
        assert form_tags.count(s.key) == s.count

    # over-ask: weights 3:2 at length 30 -> algebra 18 > 12 available
    bp_big, _, _, _ = generate_blueprint(
        GenerateBlueprintRequest(
            manifest=manifest,
            test_type="unit_quiz",
            length=30,
            kc_tag="KC",
            binding="fixed_form",
        ),
        manifest,
    )
    ok, issues, _ = check_feasibility(bp_big, pool)
    assert not ok and any(i.available == 12 and i.required > 12 for i in issues)
