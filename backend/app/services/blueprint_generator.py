"""Curriculum→blueprint generator (BP-MODES-1 §6).

Turns item-factory unit JSON (Course → Unit → KC → Complicator) into blueprints valid
under the spec, at two grains:

- **course** (EOC / mid-course test): one proportion constraint per **unit**, share
  ∝ (KCs + complicators in the unit) / (course total).
- **unit** (unit quiz): one constraint per **KC** within the chosen unit, share
  ∝ (1 + complicators in the KC).

Shares are resolved to whole item counts by **largest-remainder** rounding (counts sum
exactly to the form length) and emitted as proportion constraints with
``minimum = maximum = count / length`` — exactly recoverable by the fixed-form
compiler's ``round(p × length)``, and lenient under CAT's floor/ceil running semantics
(§3.2). Binding rules per §2.1/§4.1: CAT is content-only (a supplied TIF target is
dropped with a warning); a LOFT target must carry a tolerance (the §4.1 acceptance
band) or generation is rejected.

Feasibility (§6: generated blueprints MUST pass structural validation against the
target pool before being offered for delivery): each constraint's resolved minimum is
checked against the pool's matching-item counts — the same tag-predicate membership
the assembly compiler uses.
"""

from __future__ import annotations

import math

from app.psychometrics.bank import ItemPool
from app.schemas.blueprint import Blueprint, ContentConstraint
from app.schemas.generator import (
    CurriculumUnit,
    FeasibilityIssue,
    GenerateBlueprintRequest,
    ShareLine,
)


def largest_remainder(weights: list[int], total: int) -> list[int]:
    """Apportion ``total`` into integer counts ∝ ``weights`` (Hamilton method).

    Counts sum to exactly ``total``. Ties on the fractional remainder break toward
    the larger weight, then the earlier index — deterministic for a given input.
    """
    if total < 0:
        raise ValueError("total must be >= 0")
    if not weights or any(w < 0 for w in weights):
        raise ValueError("weights must be non-empty and non-negative")
    s = sum(weights)
    if s <= 0:
        raise ValueError("weights must sum to > 0")
    quotas = [w / s * total for w in weights]
    counts = [math.floor(q) for q in quotas]
    order = sorted(
        range(len(weights)),
        key=lambda i: (-(quotas[i] - counts[i]), -weights[i], i),
    )
    for i in order[: total - sum(counts)]:
        counts[i] += 1
    return counts


def _share_rows(req: GenerateBlueprintRequest) -> tuple[list[ShareLine], str]:
    """The §6 recipe: (key, weight) rows for the chosen grain + the tag dimension."""
    if req.grain == "course":
        rows = [
            (
                u.unit_id,
                u.unit_name,
                len(u.knowledge_components)
                + sum(len(kc.complicators) for kc in u.knowledge_components),
            )
            for u in req.units
        ]
        tag_dim = req.unit_tag
    else:  # unit quiz
        unit = _resolve_unit(req)
        rows = [
            (kc.id, kc.name, 1 + len(kc.complicators))
            for kc in unit.knowledge_components
        ]
        tag_dim = req.kc_tag

    weights = [w for _, _, w in rows]
    if sum(weights) <= 0:
        raise ValueError("curriculum has no KCs/complicators to weight shares by")
    counts = largest_remainder(weights, req.length)
    total = sum(weights)
    shares = [
        ShareLine(key=key, label=label, weight=w, share=w / total, count=n)
        for (key, label, w), n in zip(rows, counts, strict=True)
    ]
    return shares, tag_dim


def _resolve_unit(req: GenerateBlueprintRequest) -> CurriculumUnit:
    if req.unit_id is None:
        if len(req.units) == 1:
            return req.units[0]
        raise ValueError("grain='unit' with several units needs unit_id")
    for u in req.units:
        if u.unit_id == req.unit_id:
            return u
    raise ValueError(f"unit_id {req.unit_id!r} not found in the supplied units")


def generate_blueprint(
    req: GenerateBlueprintRequest,
) -> tuple[Blueprint, list[ShareLine], list[str]]:
    """Generate one blueprint; returns (blueprint, share breakdown, warnings).

    Raises ``ValueError`` on structural problems (unknown unit_id, LOFT target
    without tolerance, unweightable curriculum).
    """
    warnings: list[str] = []
    shares, tag_dim = _share_rows(req)

    # Binding rules (§2.1 / §4.1 / §6 "per binding mode").
    target = req.statistical_target
    if req.binding == "cat":
        if target is not None:
            warnings.append(
                "TIF target present on a blueprint bound to CAT delivery; it will "
                "not be enforced (BP-MODES-1 §2.1) — emitting content-only."
            )
            target = None
    elif req.binding == "loft":
        if target is not None and target.tolerance is None:
            raise ValueError(
                "LOFT binding requires a tolerance on the TIF target "
                "(BP-MODES-1 §4.1: the band is the hard acceptance criterion)"
            )
        if target is None:
            warnings.append(
                "content-only LOFT blueprint: forms will be parallel in content "
                "only, not statistically (BP-MODES-1 §2.1)."
            )
    elif target is None:  # fixed_form
        warnings.append(
            "content-only blueprint: fixed-form assembly will be feasibility-only "
            "(no TIF objective; realized TIF still reported)."
        )

    constraints = [
        ContentConstraint(
            tag_type=tag_dim,
            tag_value=s.key,
            minimum=s.count / req.length,
            maximum=s.count / req.length,
            mode="proportion",
            label=s.label,
        )
        for s in shares
    ]
    constraints.extend(req.cognitive_minimums)

    if req.name:
        name = req.name
    elif req.grain == "course":
        course = req.units[0].course_name or req.units[0].course_id or "course"
        name = f"{course} — EOC"
    else:
        unit = _resolve_unit(req)
        name = f"{unit.unit_name or unit.unit_id} — quiz"

    blueprint = Blueprint(
        name=name,
        length=req.length,
        num_forms=req.num_forms,
        content_constraints=constraints,
        statistical_target=target,
    )
    return blueprint, shares, warnings


def check_feasibility(
    blueprint: Blueprint, pool: ItemPool
) -> tuple[bool, list[FeasibilityIssue], list[str]]:
    """Structural feasibility of a blueprint against a pool (§6 gate).

    Checks each constraint's resolved minimum against the count of pool items
    matching all its tag predicates (the compiler's membership rule), plus the
    form length against the pool size. Marginal counts can't prove a combination
    of constraints feasible — this catches over-asks, the solver has the last word.
    """
    issues: list[FeasibilityIssue] = []
    notes: list[str] = []
    if blueprint.length > len(pool.items):
        issues.append(
            FeasibilityIssue(
                constraint_key="length",
                required=blueprint.length,
                available=len(pool.items),
                message=(
                    f"form length {blueprint.length} exceeds pool size "
                    f"{len(pool.items)}"
                ),
            )
        )
    for c in blueprint.content_constraints:
        minimum = c.resolved_minimum(blueprint.length)
        if not minimum:
            continue
        preds = c.predicates
        available = sum(
            1
            for it in pool.items
            if all(it.tags.get(k) == v for k, v in preds.items())
        )
        if available < minimum:
            issues.append(
                FeasibilityIssue(
                    constraint_key=c.key,
                    required=minimum,
                    available=available,
                    message=(
                        f"constraint {c.key} needs {minimum} items but only "
                        f"{available} in the pool match"
                    ),
                )
            )
    return (not issues, issues, notes)
