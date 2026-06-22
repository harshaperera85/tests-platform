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
    method: Literal["minimax", "maximin"]
    tolerance: float | None
    length: int
    num_forms: int
    content_sets: tuple[ContentSet, ...] = ()
    enemy_pairs: tuple[tuple[int, int], ...] = ()
    max_use_per_item: int | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def n_items(self) -> int:
        return len(self.item_ids)

    def tif_at(self, form_indices: list[int]) -> list[float]:
        """Actual TIF of a chosen set of item indices, at each theta point."""
        return [
            sum(self.info[i][k] for i in form_indices)
            for k in range(len(self.theta_points))
        ]


def compile_blueprint(blueprint: Blueprint, pool: ItemPool) -> CompiledProblem:
    """Translate a blueprint + pool into a :class:`CompiledProblem`."""
    items = list(pool.items)
    item_ids = tuple(it.item_id for it in items)
    index_of = {iid: i for i, iid in enumerate(item_ids)}

    theta_points = tuple(blueprint.statistical_target.theta_points)
    target_info = tuple(blueprint.statistical_target.target_info)
    info_rows = information_matrix(items, theta_points)
    info = tuple(tuple(row) for row in info_rows)

    warnings: list[str] = []

    # --- content constraints -> index member sets ---
    content_sets: list[ContentSet] = []
    for c in blueprint.content_constraints:
        members = tuple(
            i for i, it in enumerate(items) if it.tags.get(c.tag_type) == c.tag_value
        )
        if not members and c.minimum:
            warnings.append(
                f"content constraint {c.key} has minimum {c.minimum} but no pool "
                f"items match {c.tag_type}={c.tag_value}"
            )
        content_sets.append(
            ContentSet(key=c.key, members=members, minimum=c.minimum, maximum=c.maximum)
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

    max_use = (
        blueprint.exposure_target.max_use_per_item
        if blueprint.exposure_target is not None
        else None
    )

    return CompiledProblem(
        item_ids=item_ids,
        info=info,
        theta_points=theta_points,
        target_info=target_info,
        method=blueprint.statistical_target.method,
        tolerance=blueprint.statistical_target.tolerance,
        length=blueprint.length,
        num_forms=blueprint.num_forms,
        content_sets=tuple(content_sets),
        enemy_pairs=tuple(sorted(enemy_pairs)),
        max_use_per_item=max_use,
        warnings=tuple(warnings),
    )
