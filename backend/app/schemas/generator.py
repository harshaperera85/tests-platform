"""Curriculum→blueprint generator schemas (BP-MODES-1 §6).

Two layers, per the design review:

1. **Raw unit JSON** (`CurriculumUnit`) — item-factory's per-unit export, verbatim
   (verified against `outsmart-college/item-factory-source`
   `domains/*/data/unit-*.json`: one file per unit, extra keys like complicator
   ``examples``/``misconceptions`` ignored). Only the **normalizer** reads these.
2. **Curriculum manifest** (`CurriculumManifest`) — the minimal derived schema the
   generator actually consumes: course_id + units[{unit_id, order, name,
   kcs[{kc_id, order, name, complicators[{id, n_dimensions?}]}]}]. Per-complicator
   ``n_dimensions`` is the §6.1 atomic weight (from item-factory kc_configs); it is
   not in today's unit JSON export (issue #1 R7) — unknown counts are imputed.

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

from typing import Any, Literal

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
    """One sub-skill of a KC (export also carries examples/misconceptions — ignored).

    ``n_dimensions`` / ``dimensions`` are accepted for when item-factory surfaces the
    kc_config dimension counts in the export (issue #1 R7); absent today ⇒ imputed.
    """

    id: str
    order: int | None = None
    name: str | None = None
    n_dimensions: int | None = Field(default=None, ge=1)
    dimensions: list[Any] | None = None

    @property
    def dimension_count(self) -> int | None:
        if self.n_dimensions is not None:
            return self.n_dimensions
        if self.dimensions is not None and len(self.dimensions) > 0:
            return len(self.dimensions)
        return None


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
class ManifestComplicator(BaseModel):
    """One complicator in the manifest; ``n_dimensions`` is the §6.1 atomic weight
    (skills inside the complicator, from item-factory's kc_config). ``None`` ⇒ not
    yet surfaced upstream — the generator imputes the domain median and reports the
    imputed fraction (spec §6.1)."""

    id: str | None = None
    n_dimensions: int | None = Field(default=None, ge=1)


class ManifestKC(BaseModel):
    kc_id: str
    order: int | None = None
    name: str | None = None
    complicators: list[ManifestComplicator] = Field(default_factory=list)
    #: input sugar: a bare count expands to that many unknown-dimension complicators
    n_complicators: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _expand_count(self) -> ManifestKC:
        if not self.complicators and self.n_complicators:
            self.complicators = [
                ManifestComplicator() for _ in range(self.n_complicators)
            ]
        self.n_complicators = len(self.complicators)
        return self


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
    """Inputs for one generated blueprint (§6.2: one generator, one weight
    function, four scopes).

    The curriculum comes either inline (``manifest``) or from the server catalog
    (``course_id``, see ``GET /curricula``) — exactly one. ``test_type`` picks the
    §6.2 shape:

    - ``unit_quiz`` — one unit (``unit_id``): per-KC shares ∝ w(KC), plus a
      per-complicator **maximum** so a form cannot drill one complicator.
      Default binding: LOFT.
    - ``mid_course`` — first-half units; ``end_of_course`` — second-half units;
      ``cumulative_final`` — all units: per-unit shares ∝ w(unit), renormalized
      within scope. Default binding: CAT. ``scope_unit_ids`` overrides the
      derived scope for any of the three.

    Weights follow §6.1 (dimension sums with median imputation). Content-only by
    default; ``statistical_target`` optionally attaches a TIF template for
    fixed-form/LOFT bindings (LOFT requires a tolerance, §4.1).
    """

    manifest: CurriculumManifest | None = None
    course_id: str | None = None
    test_type: Literal[
        "unit_quiz", "mid_course", "end_of_course", "cumulative_final"
    ] = "cumulative_final"
    #: test_type="unit_quiz": which unit the quiz covers (defaults to the only unit)
    unit_id: str | None = None
    #: explicit unit-id scope for the CAT-shaped types (overrides the derived half)
    scope_unit_ids: list[str] | None = None
    length: int = Field(gt=0)
    num_forms: int = Field(default=1, ge=1)
    name: str | None = None
    #: None ⇒ default per test_type (unit_quiz → loft, others → cat); explicit wins
    binding: Literal["fixed_form", "loft", "cat"] | None = None
    #: unit_quiz: cap items drawn from any single complicator (1–2 per §6.2)
    max_per_complicator: int = Field(default=2, ge=1, le=2)
    #: How the content cells are encoded. Default (None) follows the binding:
    #: fixed_form/loft → count min=max (fixed length, exact allocation, §2);
    #: cat → proportion min=max (length is emergent — §3.2 interprets proportions
    #: against the realized length, while count minimums summing to a fixed-form
    #: length would be structurally impossible under a smaller max_items, §3.4(4)).
    constraint_mode: Literal["count", "proportion"] | None = None
    statistical_target: TIFTarget | None = None
    #: pool tag dimensions holding an item's unit / KC / complicator id
    unit_tag: str = "unit"
    kc_tag: str = "kc"
    complicator_tag: str = "complicator"
    cognitive_profile: CognitiveProfile | None = None
    #: validate the generated blueprint against this pool's tag counts (§6: MUST pass
    #: before being offered for delivery)
    pool_id: str | None = None

    @model_validator(mode="after")
    def _one_curriculum_source(self) -> GenerateBlueprintRequest:
        if (self.manifest is None) == (self.course_id is None):
            raise ValueError("provide exactly one of manifest or course_id")
        return self

    @property
    def resolved_binding(self) -> str:
        if self.binding is not None:
            return self.binding
        return "loft" if self.test_type == "unit_quiz" else "cat"


class ShareLine(BaseModel):
    """How one unit/KC's item share was derived (weight → share → count).

    ``weight`` is the §6.1 dimension sum (float: the domain-median imputation for
    unknown counts can be fractional). ``n_imputed`` says how many of the row's
    complicators had their dimension count imputed rather than known."""

    key: str
    label: str | None = None
    weight: float
    share: float
    count: int
    n_imputed: int = 0


class FeasibilityIssue(BaseModel):
    constraint_key: str
    required: int
    available: int
    message: str


class GenerateBlueprintResponse(BaseModel):
    blueprint: Blueprint
    shares: list[ShareLine]
    #: §6.1 honesty label: fraction of in-scope complicators whose dimension count
    #: was imputed (domain median) rather than known. 0.0 = fully data-backed.
    imputed_fraction: float = 0.0
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
