"""Curriculum→blueprint generator (BP-MODES-1 §6, rev. 2026-07-09).

Pipeline: item-factory **unit JSONs** → :func:`normalize_unit_documents` → a minimal
**curriculum manifest** → :func:`generate_blueprint`. The generator reads only
manifests.

**Weights (§6.1)** — the atomic content unit is the *dimension* (skill) inside a
complicator; weights are pure sums up the hierarchy::

    w(complicator) = n_dimensions        # ≥ 1 by construction
    w(KC)          = Σ w(complicators)
    w(unit)        = Σ w(KCs)

Where a complicator's dimension count is not yet surfaced upstream (issue #1 R7),
the **domain median** of the known counts is imputed (fallback 1.0 when nothing is
known) and the response carries the ``imputed_fraction`` — blueprints built on
partly imputed weights are honestly labeled, never silently exact.

**Test types (§6.2)** — one generator, one weight function, four scopes:

- ``unit_quiz`` (default binding LOFT): per-KC shares within one unit, **plus a
  per-complicator maximum** so a fixed form cannot drill one complicator.
- ``mid_course`` (CAT): first-half units. ``end_of_course`` (CAT): second-half
  units. ``cumulative_final`` (CAT): all units. Per-unit shares ∝ w(unit),
  renormalized within scope (``scope_unit_ids`` overrides the derived halves).

Shares resolve to whole item counts by **largest-remainder** rounding (sum exactly
to the requested length). Cell encoding follows the resolved binding unless
overridden by ``constraint_mode``: fixed-form/LOFT get **count min = max** cells
(§2 exact cells); CAT gets **proportion min = max** cells (scale-free under
emergent length, §3.2/§3.4(4)).

Feasibility (§6: generated blueprints MUST pass structural validation against the
target pool before being offered for delivery): each constraint's resolved minimum
is checked against the pool's matching-item counts — the same tag-predicate
membership the assembly compiler uses.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from pathlib import Path

import yaml

from app.psychometrics.bank import FieldPool, ItemPool
from app.schemas.blueprint import Blueprint, ContentConstraint
from app.schemas.generator import (
    CurriculumManifest,
    CurriculumUnit,
    FeasibilityIssue,
    GenerateBlueprintRequest,
    ManifestComplicator,
    ManifestKC,
    ManifestUnit,
    ShareLine,
)


def largest_remainder(weights: Sequence[float], total: int) -> list[int]:
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


def load_kc_config_dimensions(kc_configs_dir: Path) -> dict[tuple[int, int, int], int]:
    """Parse item-factory ``kc_configs/*.yml`` into dimension counts.

    Each file carries ``kc_id`` ("<unit>.<kc>", e.g. "9.1"), ``complicator`` (the
    1-based order within the KC), and ``complicator_dimensions`` (the list whose
    length is the §6.1 weight). Returns
    ``{(unit_order, kc_order, complicator_order): n_dimensions}``. Files that don't
    parse to that shape are skipped — coverage is expected to be partial (the
    imputation path owns the gaps).
    """
    out: dict[tuple[int, int, int], int] = {}
    for path in sorted(kc_configs_dir.glob("*.yml")):
        try:
            doc = yaml.safe_load(path.read_text())
            unit_s, kc_s = str(doc["kc_id"]).split(".")
            key = (int(unit_s), int(kc_s), int(doc["complicator"]))
            n = len(doc["complicator_dimensions"])
        except (KeyError, TypeError, ValueError, yaml.YAMLError):
            continue
        if n >= 1:
            out[key] = n
    return out


def normalize_unit_documents(
    docs: list[CurriculumUnit],
    *,
    kc_configs_dir: Path | None = None,
) -> CurriculumManifest:
    """Derive the minimal curriculum manifest from raw item-factory unit JSONs.

    A course = its unit files sharing ``course_id``; mixed course_ids are rejected.
    Units and KCs are ordered by their export ``order`` (input order breaks ties).
    Identifiers are carried verbatim. Per-complicator dimension counts come from,
    in priority order: the unit JSON itself (``n_dimensions`` / ``dimensions``,
    once item-factory surfaces them — issue #1 R7), else the optional
    ``kc_configs_dir`` (matched positionally: unit order × KC order × complicator
    order, the kc_config file coordinates), else left unknown for §6.1 imputation.
    """
    kc_dims: dict[tuple[int, int, int], int] = (
        load_kc_config_dimensions(kc_configs_dir) if kc_configs_dir else {}
    )
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

    def _dims(
        d: CurriculumUnit, kc_order: int | None, c_order: int | None, inline: int | None
    ) -> int | None:
        if inline is not None:  # the unit JSON itself wins once R7 lands
            return inline
        if d.unit_order is None or kc_order is None or c_order is None:
            return None
        return kc_dims.get((d.unit_order, kc_order, c_order))

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
                    complicators=[
                        ManifestComplicator(
                            id=c.id,
                            n_dimensions=_dims(
                                d, kc.order, c.order, c.dimension_count
                            ),
                        )
                        for c in kc.complicators
                    ],
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


# --------------------------------------------------------------- §6.1 weights
class _Weights:
    """Dimension-sum weights over a manifest, with domain-median imputation."""

    def __init__(self, manifest: CurriculumManifest) -> None:
        known = [
            c.n_dimensions
            for u in manifest.units
            for kc in u.kcs
            for c in kc.complicators
            if c.n_dimensions is not None
        ]
        #: imputed value for unknown dimension counts: domain median, fallback 1.0
        self.imputed_value: float = float(statistics.median(known)) if known else 1.0

    def complicator(self, c: ManifestComplicator) -> tuple[float, int]:
        """(weight, n_imputed) for one complicator."""
        if c.n_dimensions is not None:
            return float(c.n_dimensions), 0
        return self.imputed_value, 1

    def kc(self, kc: ManifestKC) -> tuple[float, int, int]:
        """(weight, n_imputed, n_complicators) — a KC with no complicators counts
        as one imputed complicator (w ≥ 1 by construction)."""
        if not kc.complicators:
            return self.imputed_value, 1, 1
        w, imp = 0.0, 0
        for c in kc.complicators:
            cw, ci = self.complicator(c)
            w += cw
            imp += ci
        return w, imp, len(kc.complicators)

    def unit(self, u: ManifestUnit) -> tuple[float, int, int]:
        """(weight, n_imputed, n_complicators) summed over the unit's KCs."""
        w, imp, n = 0.0, 0, 0
        for kc in u.kcs:
            kw, ki, kn = self.kc(kc)
            w += kw
            imp += ki
            n += kn
        return w, imp, n


# ----------------------------------------------------------------- §6.2 scope
def resolve_scope(
    manifest: CurriculumManifest, req: GenerateBlueprintRequest
) -> list[ManifestUnit]:
    """The units a test draws from, per test_type (explicit scope overrides)."""
    if req.test_type == "unit_quiz":
        return [_resolve_unit(manifest, req)]
    if req.scope_unit_ids is not None:
        by_id = {u.unit_id: u for u in manifest.units}
        missing = [i for i in req.scope_unit_ids if i not in by_id]
        if missing:
            raise ValueError(f"scope_unit_ids not in the curriculum: {missing}")
        if not req.scope_unit_ids:
            raise ValueError("scope_unit_ids must not be empty")
        return [by_id[i] for i in req.scope_unit_ids]
    n = len(manifest.units)
    first_half = manifest.units[: math.ceil(n / 2)]
    if req.test_type == "mid_course":
        return first_half
    if req.test_type == "end_of_course":
        scope = manifest.units[math.ceil(n / 2) :]
        if not scope:  # single-unit course: EOC degenerates to the whole course
            return manifest.units
        return scope
    return list(manifest.units)  # cumulative_final


def _resolve_unit(
    manifest: CurriculumManifest, req: GenerateBlueprintRequest
) -> ManifestUnit:
    if req.unit_id is None:
        if len(manifest.units) == 1:
            return manifest.units[0]
        raise ValueError("test_type='unit_quiz' with several units needs unit_id")
    for u in manifest.units:
        if u.unit_id == req.unit_id:
            return u
    raise ValueError(f"unit_id {req.unit_id!r} not found in the curriculum")


def _share_rows(
    manifest: CurriculumManifest, req: GenerateBlueprintRequest
) -> tuple[list[ShareLine], str, float]:
    """(share lines, tag dimension, imputed_fraction) for the chosen test type."""
    weights = _Weights(manifest)
    scope = resolve_scope(manifest, req)

    rows: list[tuple[str, str | None, float, int, int]] = []
    if req.test_type == "unit_quiz":
        unit = scope[0]
        for kc in unit.kcs:
            w, imp, n = weights.kc(kc)
            rows.append((kc.kc_id, kc.name, w, imp, n))
        tag_dim = req.kc_tag
    else:
        for u in scope:
            w, imp, n = weights.unit(u)
            rows.append((u.unit_id, u.name, w, imp, n))
        tag_dim = req.unit_tag

    ws = [w for _, _, w, _, _ in rows]
    if sum(ws) <= 0:
        raise ValueError("curriculum has no complicators/dimensions to weight by")
    counts = largest_remainder(ws, req.length)
    total_w = sum(ws)
    shares = [
        ShareLine(
            key=key, label=label, weight=w, share=w / total_w, count=c, n_imputed=imp
        )
        for (key, label, w, imp, _), c in zip(rows, counts, strict=True)
    ]
    n_comp = sum(n for *_, n in rows)
    n_imp = sum(imp for _, _, _, imp, _ in rows)
    imputed_fraction = (n_imp / n_comp) if n_comp else 0.0
    return shares, tag_dim, imputed_fraction


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


def _complicator_maxima(
    scope_unit: ManifestUnit, req: GenerateBlueprintRequest
) -> tuple[list[ContentConstraint], list[str]]:
    """Unit-quiz §6.2: cap items from any single complicator (id-tagged cells)."""
    out: list[ContentConstraint] = []
    n_anonymous = 0
    for kc in scope_unit.kcs:
        for c in kc.complicators:
            if c.id is None:
                n_anonymous += 1
                continue
            out.append(
                ContentConstraint(
                    tag_type=req.complicator_tag,
                    tag_value=c.id,
                    maximum=req.max_per_complicator,
                    mode="count",
                )
            )
    warnings = []
    if n_anonymous:
        warnings.append(
            f"{n_anonymous} complicator(s) have no id in the manifest — "
            "per-complicator maxima were not emitted for them"
        )
    return out, warnings


def generate_blueprint(
    req: GenerateBlueprintRequest, manifest: CurriculumManifest
) -> tuple[Blueprint, list[ShareLine], float, list[str]]:
    """Generate one blueprint; returns (blueprint, shares, imputed_fraction,
    warnings).

    ``manifest`` is the resolved curriculum (inline or from the catalog — the
    caller resolves ``course_id``). Raises ``ValueError`` on structural problems
    (unknown unit_id/scope, LOFT target without tolerance, unweightable
    curriculum).
    """
    warnings: list[str] = []
    shares, tag_dim, imputed_fraction = _share_rows(manifest, req)
    if imputed_fraction > 0:
        n_imp = sum(s.n_imputed for s in shares)
        warnings.append(
            f"{n_imp} in-scope complicator dimension count(s) imputed at the "
            f"domain median ({imputed_fraction:.0%} of scope) — weights are "
            "honest estimates, not exact (BP-MODES-1 §6.1)"
        )

    # Binding rules (§2.1 / §4.1); default binding per test type (§6.2).
    binding = req.resolved_binding
    target = req.statistical_target
    if binding == "cat":
        if target is not None:
            warnings.append(
                "TIF target present on a blueprint bound to CAT delivery; it will "
                "not be enforced (BP-MODES-1 §2.1) — emitting content-only."
            )
            target = None
    elif binding == "loft":
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
    cell_mode = req.constraint_mode or ("proportion" if binding == "cat" else "count")
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

    if req.test_type == "unit_quiz":
        maxima, w = _complicator_maxima(_resolve_unit(manifest, req), req)
        constraints.extend(maxima)
        warnings.extend(w)

    constraints.extend(_cognitive_constraints(manifest, req))

    if req.name:
        name = req.name
    else:
        course = manifest.course_name or manifest.course_id
        if req.test_type == "unit_quiz":
            unit = _resolve_unit(manifest, req)
            name = f"{unit.name or unit.unit_id} — quiz"
        else:
            suffix = {
                "mid_course": "mid-course",
                "end_of_course": "end-of-course",
                "cumulative_final": "cumulative final",
            }[req.test_type]
            name = f"{course} — {suffix}"

    blueprint = Blueprint(
        name=name,
        length=req.length,
        num_forms=req.num_forms,
        content_constraints=constraints,
        statistical_target=target,
    )
    return blueprint, shares, imputed_fraction, warnings


def check_feasibility(
    blueprint: Blueprint, pool: ItemPool | FieldPool
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
