"""Curriculum→blueprint generator schemas (BP-MODES-1 §6).

Two layers, per the design review:

1. **Raw unit JSON** (`CurriculumUnit`) — item-factory's per-unit export, verbatim
   (verified against `outsmart-college/item-factory-source`
   `domains/*/data/unit-*.json`: one file per unit, extra keys like complicator
   ``examples``/``misconceptions`` ignored). Only the **normalizer** reads these.
2. **Curriculum manifest** (`CurriculumManifest`) — the minimal derived schema the
   generator actually consumes: course_id + units[{unit_id, order, name,
   kcs[{kc_id, order, name, n_complicators}]}].

Unit/KC identifiers are carried **exactly as they appear in the unit JSONs** — never
re-minted; the pool importer will use the same ones.

Cognitive constraints are an AUTHORED input (`CognitiveProfile`), never derived from
the curriculum: tagging happens once, in item-factory, at template-authoring time
(TemplateSpec) — cognitive tags are read-only imported item attributes here. The only
dimensions that exist on items (pinned 2026-07-07; Bloom is two-dimensional, never a
generic "bloom"; DOK is not tagged upstream yet):
``bloom_process`` / ``bloom_knowledge`` / ``timss``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.blueprint import Blueprint, TIFTarget

#: The pinned cognitive tag contract: dimension → allowed values (item attributes
#: authored in item-factory; pool tag names follow its export_cat_ready() fields).
COGNITIVE_DIMENSIONS: dict[str, frozenset[str]] = {
    "bloom_process": frozenset(
        {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"}
    ),
    "bloom_knowledge": frozenset(
        {"Factual", "Conceptual", "Procedural", "Metacognitive"}
    ),
    "timss": frozenset({"Knowing", "Applying", "Reasoning"}),
}


# ------------------------------------------------------------- raw unit JSON layer
class CurriculumComplicator(BaseModel):
    """One sub-skill of a KC (export also carries examples/misconceptions — ignored)."""

    id: str
    order: int | None = None
    name: str | None = None


class CurriculumKC(BaseModel):
    id: str
    order: int | None = None
    name: str | None = None
    complicators: list[CurriculumComplicator] = Field(default_factory=list)


class CurriculumUnit(BaseModel):
    """One item-factory unit JSON file, verbatim."""

    course_id: str | None = None
    course_name: str | None = None
    unit_id: str
    unit_order: int | None = None
    unit_name: str | None = None
    knowledge_components: list[CurriculumKC] = Field(min_length=1)


# ------------------------------------------------------------------ manifest layer
class ManifestKC(BaseModel):
    kc_id: str
    order: int | None = None
    name: str | None = None
    n_complicators: int = Field(default=0, ge=0)


class ManifestUnit(BaseModel):
    unit_id: str
    order: int | None = None
    name: str | None = None
    kcs: list[ManifestKC] = Field(min_length=1)


class CurriculumManifest(BaseModel):
    """The minimal curriculum shape the generator reads (derived from unit JSONs)."""

    course_id: str
    course_name: str | None = None
    units: list[ManifestUnit] = Field(min_length=1)


# ------------------------------------------------------------- cognitive profile
class PerUnitCognitiveMinimum(BaseModel):
    """A cross-classified cell minimum: at least ``minimum`` items in ``unit_id``
    carrying ``value`` on the profile's dimension."""

    unit_id: str
    value: str
    minimum: int = Field(ge=1)


class CognitiveProfile(BaseModel):
    """Authored cognitive requirements (never derived from the curriculum).

    ``distribution`` (value → share of the form, shares summing to 1) is emitted as
    marginal proportion constraints; ``per_unit_minimums`` as cross-classified
    {unit × dimension} count minimums. ``dimension`` and every value are validated
    against the pinned :data:`COGNITIVE_DIMENSIONS` contract.
    """

    dimension: Literal["bloom_process", "bloom_knowledge", "timss"]
    distribution: dict[str, float] | None = None
    per_unit_minimums: list[PerUnitCognitiveMinimum] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> CognitiveProfile:
        allowed = COGNITIVE_DIMENSIONS[self.dimension]
        if self.distribution is not None:
            if not self.distribution:
                raise ValueError("distribution must not be empty")
            unknown = set(self.distribution) - allowed
            if unknown:
                raise ValueError(
                    f"unknown {self.dimension} value(s) {sorted(unknown)}; "
                    f"allowed: {sorted(allowed)}"
                )
            if any(v <= 0 for v in self.distribution.values()):
                raise ValueError("distribution shares must be > 0")
            total = sum(self.distribution.values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"distribution shares must sum to 1 (got {total})")
        for m in self.per_unit_minimums:
            if m.value not in allowed:
                raise ValueError(
                    f"unknown {self.dimension} value {m.value!r}; "
                    f"allowed: {sorted(allowed)}"
                )
        if self.distribution is None and not self.per_unit_minimums:
            raise ValueError(
                "cognitive_profile needs a distribution and/or per_unit_minimums"
            )
        return self


# --------------------------------------------------------------- request/response
class GenerateBlueprintRequest(BaseModel):
    """Inputs for one generated blueprint.

    The curriculum comes either inline (``manifest``) or from the server catalog
    (``course_id``, see ``GET /curricula``) — exactly one. ``grain`` picks the §6
    recipe: ``eoc`` = end-of-course / mid-course test (one count constraint per
    **unit**, share ∝ KCs + complicators in the unit); ``unit_quiz`` = one
    constraint per **KC** within ``unit_id`` (share ∝ 1 + complicators).
    Content-only by default; ``statistical_target`` optionally attaches a TIF
    template for fixed-form/LOFT bindings (LOFT requires a tolerance, §4.1).
    """

    manifest: CurriculumManifest | None = None
    course_id: str | None = None
    grain: Literal["eoc", "unit_quiz"] = "eoc"
    #: grain="unit_quiz": which unit the quiz covers (defaults to the only unit)
    unit_id: str | None = None
    length: int = Field(gt=0)
    num_forms: int = Field(default=1, ge=1)
    name: str | None = None
    binding: Literal["fixed_form", "loft", "cat"] = "fixed_form"
    statistical_target: TIFTarget | None = None
    #: pool tag dimensions holding an item's unit / KC id
    unit_tag: str = "unit"
    kc_tag: str = "kc"
    cognitive_profile: CognitiveProfile | None = None
    #: validate the generated blueprint against this pool's tag counts (§6: MUST pass
    #: before being offered for delivery)
    pool_id: str | None = None

    @model_validator(mode="after")
    def _one_curriculum_source(self) -> GenerateBlueprintRequest:
        if (self.manifest is None) == (self.course_id is None):
            raise ValueError("provide exactly one of manifest or course_id")
        return self


class ShareLine(BaseModel):
    """How one unit/KC's item share was derived (weight → share → count)."""

    key: str
    label: str | None = None
    weight: int
    share: float
    count: int


class FeasibilityIssue(BaseModel):
    constraint_key: str
    required: int
    available: int
    message: str


class GenerateBlueprintResponse(BaseModel):
    blueprint: Blueprint
    shares: list[ShareLine]
    #: True when a pool_id was supplied and the check ran
    feasibility_checked: bool
    feasible: bool
    issues: list[FeasibilityIssue]
    warnings: list[str]


# ----------------------------------------------------------------- catalog views
class CurriculumSummary(BaseModel):
    """One catalog entry for the UI's course picker."""

    course_id: str
    course_name: str | None = None
    n_units: int
    n_kcs: int
    units: list[ManifestUnit]
