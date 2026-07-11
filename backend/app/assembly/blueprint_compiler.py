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

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from app.psychometrics.bank import FieldItem, FieldPool, ItemPool
from app.psychometrics.information import information_matrix, prob_correct
from app.psychometrics.params import ItemParameters
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
    #: expected-score (TCC) band (G4): ``prob[i][k]`` is item i's P(θ) at
    #: ``tcc_theta_points[k]``; the band is HARD ``|TCC_k − tcc_target_k| ≤
    #: tcc_tolerance``. All empty/None ⇒ no TCC machinery, model unchanged.
    prob: tuple[tuple[float, ...], ...] = ()
    tcc_theta_points: tuple[float, ...] = ()
    tcc_target: tuple[float, ...] = ()
    tcc_tolerance: float | None = None

    @property
    def n_items(self) -> int:
        return len(self.item_ids)

    def tif_at(self, form_indices: list[int]) -> list[float]:
        """Actual TIF of a chosen set of item indices, at each theta point."""
        return [
            sum(self.info[i][k] for i in form_indices)
            for k in range(len(self.theta_points))
        ]

    def tcc_at(self, form_indices: list[int]) -> list[float]:
        """Actual expected score at each TCC theta point (empty if no target)."""
        return [
            sum(self.prob[i][k] for i in form_indices)
            for k in range(len(self.tcc_theta_points))
        ]


def compile_blueprint(
    blueprint: Blueprint,
    pool: ItemPool | FieldPool,
    *,
    exposure_counts: dict[str, int] | None = None,
) -> CompiledProblem:
    """Translate a blueprint + pool into a :class:`CompiledProblem`.

    A :class:`FieldPool` (content-only field-study pool, no parameters) is
    accepted ONLY with a content-only blueprint: assembly is pure feasibility,
    no information is computed (none exists), and no realized TIF is reported —
    honestly absent rather than fabricated.

    ``exposure_counts`` (cumulative usage per item_id) is only consulted when the
    blueprint declares ``exposure_feedback``; otherwise the compiled problem is
    identical to a no-exposure compile (assembly behavior unchanged).
    """
    items: Sequence[ItemParameters | FieldItem] = list(pool.items)
    item_ids = tuple(it.item_id for it in items)
    index_of = {iid: i for i, iid in enumerate(item_ids)}

    is_field = isinstance(pool, FieldPool)
    tgt = blueprint.statistical_target
    if is_field and tgt is not None:
        raise ValueError(
            "field-study pools are content-only: they carry no parameters, so a "
            "blueprint with a statistical (TIF) target cannot be assembled from "
            "one — remove the target (content-only blueprint) or use a "
            "calibrated pool"
        )
    tcc = blueprint.tcc_target
    if is_field and tcc is not None:
        raise ValueError(
            "field-study pools are content-only: they carry no parameters, so a "
            "blueprint with a TCC (expected-score) target cannot be assembled "
            "from one"
        )

    # Content-only blueprint (no TIF target): assemble for feasibility only, but
    # still report realized TIF at a default grid — except on field pools, where
    # no parameters exist and nothing is reported. Targeted blueprints unchanged.
    feasibility_only = tgt is None
    info: tuple[tuple[float, ...], ...]
    params: tuple[tuple[float, float, float, float], ...]
    if is_field:
        theta_points: tuple[float, ...] = ()
        target_info: tuple[float, ...] = ()
        info = tuple(() for _ in items)
        params = ()
    else:
        cal_items = cast("list[ItemParameters]", items)
        if tgt is None:
            theta_points = DEFAULT_REPORT_THETA
            target_info = ()
        else:
            theta_points = tuple(tgt.theta_points)
            target_info = tuple(tgt.target_info)
        info_rows = information_matrix(cal_items, theta_points)
        info = tuple(tuple(row) for row in info_rows)
        params = tuple((it.a, it.d, it.c, it.u) for it in cal_items)

    # --- TCC (expected-score) band: per-item P(θ) at the TCC theta points ---
    prob: tuple[tuple[float, ...], ...] = ()
    tcc_theta_points: tuple[float, ...] = ()
    tcc_target_scores: tuple[float, ...] = ()
    if tcc is not None:
        cal = cast("list[ItemParameters]", items)
        tcc_theta_points = tuple(tcc.theta_points)
        tcc_target_scores = tuple(tcc.target_scores)
        prob = tuple(
            tuple(prob_correct(it, t) for t in tcc_theta_points) for it in cal
        )

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
        params=params,
        excluded_indices=excluded_indices,
        exposure=exposure_vec,
        underuse_weight=underuse_weight,
        feasibility_only=feasibility_only,
        prob=prob,
        tcc_theta_points=tcc_theta_points,
        tcc_target=tcc_target_scores,
        tcc_tolerance=tcc.tolerance if tcc is not None else None,
    )
