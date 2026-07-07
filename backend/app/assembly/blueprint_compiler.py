"""Compile a :class:`Blueprint` + item pool into a solver-ready problem.

This is the seam between the model-independent blueprint (content + TIF targets)
and the assembly engine (plan §6 pipeline:
``Blueprint -> blueprint_compiler -> constraints + objective -> strategy``).

The compiler resolves:
- the per-item information matrix at the blueprint's theta points (via the canonical
  psychometrics layer),
- content constraints into item-index member sets with lower/upper bounds,
- enemy ``enemy_of`` relations into symmetric index pairs,
- length, number of forms, exposure cap, and the TIF objective parameters.

It performs no solving; it owns the *translation* only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.psychometrics.bank import ItemPool
from app.psychometrics.information import information_matrix
from app.schemas.blueprint import Blueprint

#: Theta grid used to *report* realized TIF for a content-only blueprint (one with no
#: ``statistical_target``). Matches the QA / comparability reporting grid (−3 … 3 by
#: 0.5) so the reported information curve is consistent across the app. Only used when
#: there is no author-supplied target; targeted blueprints report at their own points.
DEFAULT_REPORT_THETA: tuple[float, ...] = tuple(
    round(-3.0 + 0.5 * i, 3) for i in range(13)
)


@dataclass(frozen=True)
class ContentSet:
    """A content constraint resolved to item indices into the problem's item list."""

    key: str
    members: tuple[int, ...]
    minimum: int | None
    maximum: int | None


@dataclass(frozen=True)
class CompiledProblem:
    """Everything a strategy needs to assemble, with nothing it doesn't.

    ``info[i][k]`` is item ``i``'s Fisher information at ``theta_points[k]``.
    """

    item_ids: tuple[str, ...]
    info: tuple[tuple[float, ...], ...]
    theta_points: tuple[float, ...]
    target_info: tuple[float, ...]
    method: Literal["minimax", "maximin", "none"]
    tolerance: float | None
    length: int
    num_forms: int
    content_sets: tuple[ContentSet, ...] = ()
    enemy_pairs: tuple[tuple[int, int], ...] = ()
    max_use_per_item: int | None = None
    max_pairwise_overlap: int | None = None
    # per-theta minimax weights (all 1.0 = unweighted minimax)
    weights: tuple[float, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)
    # native canonical slope-intercept params per item: (a, d, g=c, u). Lets the R
    # oracle receive mirt-native parameters (D=1 slope-intercept), not just the
    # precomputed info matrix.
    params: tuple[tuple[float, float, float, float], ...] = ()
    # longitudinal-exposure eligibility (opt-in; empty/0 ⇒ no effect, identical model):
    # item indices hard-excluded (over-exposed) + per-item cumulative exposure +
    # under-use objective weight (info-units per unit of exposure).
    excluded_indices: tuple[int, ...] = ()
    exposure: tuple[int, ...] = ()
    underuse_weight: float = 0.0
    #: content-only blueprint (BP-MODES-1 A1): assemble for feasibility only — no TIF
    #: objective — while still reporting realized TIF (``target_info`` is then empty and
    #: ``theta_points`` is the reporting grid). Default False ⇒ targeted assembly is
    #: byte-for-byte unchanged.
    feasibility_only: bool = False

    @property
    def n_items(self) -> int:
        return len(self.item_ids)

    def tif_at(self, form_indices: list[int]) -> list[float]:
        """Actual TIF of a chosen set of item indices, at each theta point."""
        return [
            sum(self.info[i][k] for i in form_indices)
            for k in range(len(self.theta_points))
        ]


def compile_blueprint(
    blueprint: Blueprint,
    pool: ItemPool,
    *,
    exposure_counts: dict[str, int] | None = None,
) -> CompiledProblem:
    """Translate a blueprint + pool into a :class:`CompiledProblem`.

    ``exposure_counts`` (cumulative usage per item_id) is only consulted when the
    blueprint declares ``exposure_feedback``; otherwise the compiled problem is
    identical to a no-exposure compile (assembly behavior unchanged).
    """
    items = list(pool.items)
    item_ids = tuple(it.item_id for it in items)
    index_of = {iid: i for i, iid in enumerate(item_ids)}

    # Content-only blueprint (no TIF target): assemble for feasibility only, but
    # still report realized TIF at a default grid. Targeted blueprints are unchanged.
    tgt = blueprint.statistical_target
    feasibility_only = tgt is None
    if tgt is None:
        theta_points = DEFAULT_REPORT_THETA
        target_info: tuple[float, ...] = ()
    else:
        theta_points = tuple(tgt.theta_points)
        target_info = tuple(tgt.target_info)
    info_rows = information_matrix(items, theta_points)
    info = tuple(tuple(row) for row in info_rows)

    warnings: list[str] = []

    # --- content constraints -> index member sets ---
    # An item is a member iff it matches ALL of the constraint's tag predicates
    # (marginal = one predicate; cross-classified cell = several). Proportion bounds
    # are resolved to counts against the form length here.
    content_sets: list[ContentSet] = []
    for c in blueprint.content_constraints:
        preds = c.predicates
        members = tuple(
            i
            for i, it in enumerate(items)
            if all(it.tags.get(k) == v for k, v in preds.items())
        )
        minimum = c.resolved_minimum(blueprint.length)
        maximum = c.resolved_maximum(blueprint.length)
        if not members and minimum:
            warnings.append(
                f"content constraint {c.key} has minimum {minimum} but no pool "
                f"items match {c.key}"
            )
        content_sets.append(
            ContentSet(key=c.key, members=members, minimum=minimum, maximum=maximum)
        )

    # --- enemy relations -> symmetric, deduped index pairs ---
    enemy_pairs: set[tuple[int, int]] = set()
    if blueprint.enemy_policy.enforce:
        for i, it in enumerate(items):
            for other_id in it.enemy_of:
                j = index_of.get(other_id)
                if j is None or j == i:
                    continue
                enemy_pairs.add((min(i, j), max(i, j)))

    # Exposure: resolve the per-item use cap (raw override, else rate × num_forms)
    # and the pairwise-overlap cap from the exposure target.
    max_use: int | None = None
    max_pairwise_overlap: int | None = None
    exp = blueprint.exposure_target
    if exp is not None:
        max_use = exp.resolved_max_use(blueprint.num_forms)
        max_pairwise_overlap = exp.max_pairwise_overlap

    # Longitudinal-exposure feedback (opt-in). Absent ⇒ excluded/exposure/weight stay
    # empty/0 and the compiled problem is identical to a no-exposure compile.
    excluded_indices: tuple[int, ...] = ()
    exposure_vec: tuple[int, ...] = ()
    underuse_weight = 0.0
    fb = blueprint.exposure_feedback
    if fb is not None:
        counts = exposure_counts or {}
        if fb.max_cumulative is not None:
            excluded_indices = tuple(
                i
                for i, iid in enumerate(item_ids)
                if counts.get(iid, 0) >= fb.max_cumulative
            )
            n_elig = len(items) - len(excluded_indices)
            if n_elig < blueprint.length:
                warnings.append(
                    f"exposure feedback excluded {len(excluded_indices)} over-exposed "
                    f"items; only {n_elig} eligible for length {blueprint.length}"
                )
        if fb.prefer_underused and fb.underuse_weight > 0:
            exposure_vec = tuple(counts.get(iid, 0) for iid in item_ids)
            underuse_weight = fb.underuse_weight

    return CompiledProblem(
        item_ids=item_ids,
        info=info,
        theta_points=theta_points,
        target_info=target_info,
        method=tgt.method if tgt is not None else "none",
        tolerance=tgt.tolerance if tgt is not None else None,
        length=blueprint.length,
        num_forms=blueprint.num_forms,
        content_sets=tuple(content_sets),
        enemy_pairs=tuple(sorted(enemy_pairs)),
        max_use_per_item=max_use,
        max_pairwise_overlap=max_pairwise_overlap,
        weights=tgt.resolved_weights if tgt is not None else (),
        warnings=tuple(warnings),
        params=tuple((it.a, it.d, it.c, it.u) for it in items),
        excluded_indices=excluded_indices,
        exposure=exposure_vec,
        underuse_weight=underuse_weight,
        feasibility_only=feasibility_only,
    )
