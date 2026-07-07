"""Curriculum→blueprint generator schemas (BP-MODES-1 §6).

The generator consumes item-factory **unit JSON** files verbatim (verified against
`outsmart-college/item-factory-source` `domains/*/data/unit-*.json`, 2026-07-07: one
file per unit, all sharing exactly this shape) and emits blueprints valid under
BP-MODES-1. Extra keys in the export (`examples`, `misconceptions` on complicators)
are ignored on parse.

    {"course_id": …, "course_name": …, "unit_id": …, "unit_order": …,
     "unit_name": …, "knowledge_components": [
        {"id": …, "order": …, "name": …, "complicators": [{"id": …, …}]}]}

Constraint tag *values* are the export's stable ids (`unit_id`, KC `id`); the pool tag
*dimensions* holding them are configurable (item-factory change-request R3 flat tags).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.blueprint import Blueprint, ContentConstraint, TIFTarget


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


class GenerateBlueprintRequest(BaseModel):
    """Inputs for one generated blueprint.

    ``units`` is the curriculum: one or more item-factory unit JSON documents (a
    course = its unit files). ``grain`` picks the §6 recipe: ``course`` = EOC /
    mid-course test (one proportion constraint per **unit**, share ∝ KCs +
    complicators in the unit); ``unit`` = unit quiz (one constraint per **KC**
    within ``unit_id``, share ∝ 1 + complicators). ``binding`` applies the per-mode
    target rule: content-only for CAT; a TIF target (with tolerance, for LOFT)
    attached for fixed-form/LOFT bindings.
    """

    units: list[CurriculumUnit] = Field(min_length=1)
    grain: Literal["course", "unit"] = "course"
    #: grain="unit": which unit the quiz covers (defaults to the only unit given)
    unit_id: str | None = None
    length: int = Field(gt=0)
    num_forms: int = Field(default=1, ge=1)
    name: str | None = None
    binding: Literal["fixed_form", "loft", "cat"] = "fixed_form"
    statistical_target: TIFTarget | None = None
    #: pool tag dimensions holding an item's unit / KC id (item-factory R3 flat tags)
    unit_tag: str = "unit"
    kc_tag: str = "kc"
    #: optional cognitive minimums (Bloom's / DOK / TIMSS per program), passed through
    cognitive_minimums: list[ContentConstraint] = Field(default_factory=list)
    #: validate the generated blueprint against this pool's tag counts (§6: MUST pass
    #: before being offered for delivery)
    pool_id: str | None = None


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
