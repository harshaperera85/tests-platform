"""Curriculum→blueprint generator (BP-MODES-1 §6).

Pipeline: item-factory **unit JSONs** → :func:`normalize_unit_documents` → a minimal
**curriculum manifest** → :func:`generate_blueprint`. The generator reads only
manifests.

Recipes (shares → whole item counts by **largest-remainder** rounding, summing exactly
to the requested length). Cell encoding follows the binding unless overridden by
``constraint_mode``: fixed-form/LOFT get **count min = max** cells (fixed length,
exact allocation, §2); CAT gets **proportion min = max** cells (length is emergent —
§3.2 interprets proportions against the realized length with floor/ceil slack,
whereas count minimums summing to a fixed-form length would be structurally
impossible under a smaller ``max_items``, §3.4(4)):

- **eoc** (end-of-course / mid-course): one constraint per **unit**, share
  ∝ (KCs + complicators in the unit) / course totals.
- **unit_quiz**: one constraint per **KC** in the chosen unit, share
  ∝ (1 + complicators in the KC).

The **cognitive profile** is an authored input (tags are read-only item-factory
attributes — see ``schemas.generator.COGNITIVE_DIMENSIONS``): a distribution becomes
marginal proportion constraints (largest-remainder over the length, then
``count/length`` so the compiler's ``round(p × L)`` recovers the counts exactly);
per-unit minimums become cross-classified {unit × dimension} count cells.

Binding rules per §2.1/§4.1: content-only is the default; CAT drops a supplied TIF
target with a warning; a LOFT target must carry a tolerance (the §4.1 acceptance band)
or generation is rejected.

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
    CurriculumManifest,
    CurriculumUnit,
    FeasibilityIssue,
    GenerateBlueprintRequest,
    ManifestKC,
    ManifestUnit,
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


def normalize_unit_documents(docs: list[CurriculumUnit]) -> CurriculumManifest:
    """Derive the minimal curriculum manifest from raw item-factory unit JSONs.

    A course = its unit files sharing ``course_id``; mixed course_ids are rejected.
    Units and KCs are ordered by their export ``order`` (input order breaks ties).
    Identifiers are carried verbatim.
    """
    if not docs:
        raise ValueError("no unit documents supplied")
    course_ids = {d.course_id for d in docs if d.course_id is not None}
    if len(course_ids) > 1:
        raise ValueError(
            f"unit documents span several course_ids: {sorted(course_ids)}"
        )
    seen: set[str] = set()
    for d in docs:
        if d.unit_id in seen:
            raise ValueError(f"duplicate unit_id {d.unit_id!r} in unit documents")
        seen.add(d.unit_id)

    ordered = sorted(
        enumerate(docs), key=lambda p: (p[1].unit_order is None, p[1].unit_order, p[0])
    )
    units = [
        ManifestUnit(
            unit_id=d.unit_id,
            order=d.unit_order,
            name=d.unit_name,
            kcs=[
                ManifestKC(
                    kc_id=kc.id,
                    order=kc.order,
                    name=kc.name,
                    n_complicators=len(kc.complicators),
                )
                for kc in sorted(
                    d.knowledge_components,
                    key=lambda k: (k.order is None, k.order),
                )
            ],
        )
        for _, d in ordered
    ]
    return CurriculumManifest(
        course_id=next(iter(course_ids), "unknown-course"),
        course_name=next((d.course_name for d in docs if d.course_name), None),
        units=units,
    )


def _share_rows(
    manifest: CurriculumManifest, req: GenerateBlueprintRequest
) -> tuple[list[ShareLine], str]:
    """The §6 recipe: (key, weight) rows for the chosen grain + the tag dimension."""
    if req.grain == "eoc":
        rows = [
            (
                u.unit_id,
                u.name,
                len(u.kcs) + sum(kc.n_complicators for kc in u.kcs),
            )
            for u in manifest.units
        ]
        tag_dim = req.unit_tag
    else:  # unit_quiz
        unit = _resolve_unit(manifest, req)
        rows = [(kc.kc_id, kc.name, 1 + kc.n_complicators) for kc in unit.kcs]
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


def _resolve_unit(
    manifest: CurriculumManifest, req: GenerateBlueprintRequest
) -> ManifestUnit:
    if req.unit_id is None:
        if len(manifest.units) == 1:
            return manifest.units[0]
        raise ValueError("grain='unit_quiz' with several units needs unit_id")
    for u in manifest.units:
        if u.unit_id == req.unit_id:
            return u
    raise ValueError(f"unit_id {req.unit_id!r} not found in the curriculum")


def _cognitive_constraints(
    manifest: CurriculumManifest, req: GenerateBlueprintRequest
) -> list[ContentConstraint]:
    """Authored cognitive profile → marginal proportions + cross-classified cells."""
    profile = req.cognitive_profile
    if profile is None:
        return []
    out: list[ContentConstraint] = []

    if profile.distribution:
        values = list(profile.distribution.keys())
        counts = largest_remainder(
            # scale shares to integers to keep largest_remainder exact-friendly
            [round(profile.distribution[v] * 1_000_000) for v in values],
            req.length,
        )
        for value, count in zip(values, counts, strict=True):
            out.append(
                ContentConstraint(
                    tag_type=profile.dimension,
                    tag_value=value,
                    minimum=count / req.length,
                    maximum=count / req.length,
                    mode="proportion",
                )
            )

    known_units = {u.unit_id for u in manifest.units}
    for m in profile.per_unit_minimums:
        if m.unit_id not in known_units:
            raise ValueError(
                f"per_unit_minimums references unknown unit_id {m.unit_id!r}"
            )
        out.append(
            ContentConstraint(
                tags={req.unit_tag: m.unit_id, profile.dimension: m.value},
                minimum=m.minimum,
                mode="count",
            )
        )
    return out


def generate_blueprint(
    req: GenerateBlueprintRequest, manifest: CurriculumManifest
) -> tuple[Blueprint, list[ShareLine], list[str]]:
    """Generate one blueprint; returns (blueprint, share breakdown, warnings).

    ``manifest`` is the resolved curriculum (inline or from the catalog — the
    caller resolves ``course_id``). Raises ``ValueError`` on structural problems
    (unknown unit_id, LOFT target without tolerance, unweightable curriculum).
    """
    warnings: list[str] = []
    shares, tag_dim = _share_rows(manifest, req)

    # Binding rules (§2.1 / §4.1). Content-only is the default — no warning for
    # fixed-form; LOFT content-only gets the §2.1(2) authoring notice.
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

    # Cell encoding: counts for fixed-length bindings (§2 exact cells); proportions
    # for CAT (scale-free under emergent length, §3.2). Explicit override wins.
    cell_mode = req.constraint_mode or (
        "proportion" if req.binding == "cat" else "count"
    )
    if cell_mode == "count":
        constraints = [
            ContentConstraint(
                tag_type=tag_dim,
                tag_value=s.key,
                minimum=s.count,
                maximum=s.count,
                mode="count",
                label=s.label,
            )
            for s in shares
        ]
    else:
        # min = max = count/length round-trips exactly through the fixed-form
        # compiler's round(p × L) and scales with a CAT session's realized length.
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
    constraints.extend(_cognitive_constraints(manifest, req))

    if req.name:
        name = req.name
    elif req.grain == "eoc":
        name = f"{manifest.course_name or manifest.course_id} — EOC"
    else:
        unit = _resolve_unit(manifest, req)
        name = f"{unit.name or unit.unit_id} — quiz"

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
