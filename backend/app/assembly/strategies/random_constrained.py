"""``random_constrained`` — weighted-random assembly honoring hard constraints.

The low-rigor end of the assembly spectrum (plan §6): fast, content/enemy/length/
exposure feasible, but it does **not** optimize the TIF — it reports the realized
TIF so the miss is visible. Appropriate for low-stakes forms or as a feasibility
baseline against the ``mip`` strategy. Deterministic given ``seed``.
"""

from __future__ import annotations

import random

from app.assembly.blueprint_compiler import CompiledProblem
from app.assembly.result import AssemblyResult, FormSolution
from app.assembly.strategies.base import AssemblyStrategy, register_strategy

_MAX_ATTEMPTS = 400


@register_strategy
class RandomConstrainedStrategy(AssemblyStrategy):
    name = "random_constrained"

    def assemble(
        self,
        problem: CompiledProblem,
        *,
        time_limit_s: float = 10.0,
        seed: int = 0,
    ) -> AssemblyResult:
        rng = random.Random(seed)
        n = problem.n_items

        enemies: list[set[int]] = [set() for _ in range(n)]
        for i, j in problem.enemy_pairs:
            enemies[i].add(j)
            enemies[j].add(i)

        # item index -> content-set indices it belongs to (for maximum tracking)
        member_sets: list[list[int]] = [[] for _ in range(n)]
        for csi, cs in enumerate(problem.content_sets):
            for i in cs.members:
                member_sets[i].append(csi)

        used_across_forms = [0] * n
        forms: list[FormSolution] = []

        for _ in range(problem.num_forms):
            chosen = self._assemble_one(
                problem, rng, enemies, member_sets, used_across_forms
            )
            if chosen is None:
                return AssemblyResult(
                    strategy=self.name,
                    status="infeasible",
                    theta_points=list(problem.theta_points),
                    target_info=list(problem.target_info),
                    method=problem.method,
                    warnings=[
                        *problem.warnings,
                        "random_constrained exhausted attempts; problem may be "
                        "infeasible or too tight for random search (try mip)",
                    ],
                )
            for i in chosen:
                used_across_forms[i] += 1
            forms.append(
                FormSolution(
                    item_ids=[problem.item_ids[i] for i in chosen],
                    tif_actual=problem.tif_at(chosen),
                )
            )

        obj = max(
            abs(f.tif_actual[k] - problem.target_info[k])
            for f in forms
            for k in range(len(problem.theta_points))
        )
        return AssemblyResult(
            strategy=self.name,
            status="feasible",
            theta_points=list(problem.theta_points),
            target_info=list(problem.target_info),
            method=problem.method,
            forms=forms,
            objective_value=obj,
            warnings=list(problem.warnings),
        )

    def _assemble_one(
        self,
        problem: CompiledProblem,
        rng: random.Random,
        enemies: list[set[int]],
        member_sets: list[list[int]],
        used_across_forms: list[int],
    ) -> list[int] | None:
        for _ in range(_MAX_ATTEMPTS):
            builder = _FormBuilder(problem, enemies, member_sets, used_across_forms)
            if builder.try_build(rng):
                return sorted(builder.chosen)
        return None


class _FormBuilder:
    """Mutable accumulator for one random assembly attempt.

    Holding state on an instance (rather than in closures inside the attempt loop)
    keeps the feasibility helpers free of loop-variable capture.
    """

    def __init__(
        self,
        problem: CompiledProblem,
        enemies: list[set[int]],
        member_sets: list[list[int]],
        used_across_forms: list[int],
    ) -> None:
        self.problem = problem
        self.enemies = enemies
        self.member_sets = member_sets
        self.used = used_across_forms
        self.max_use = problem.max_use_per_item
        self.chosen: list[int] = []
        self.chosen_set: set[int] = set()
        self.counts = [0] * len(problem.content_sets)

    def can_add(self, i: int) -> bool:
        if i in self.chosen_set:
            return False
        if self.max_use is not None and self.used[i] >= self.max_use:
            return False
        if self.enemies[i] & self.chosen_set:
            return False
        for csi in self.member_sets[i]:
            cs = self.problem.content_sets[csi]
            if cs.maximum is not None and self.counts[csi] + 1 > cs.maximum:
                return False
        return True

    def add(self, i: int) -> None:
        self.chosen.append(i)
        self.chosen_set.add(i)
        for csi in self.member_sets[i]:
            self.counts[csi] += 1

    def try_build(self, rng: random.Random) -> bool:
        p = self.problem
        # Phase 1: satisfy minimums.
        for csi, cs in enumerate(p.content_sets):
            if not cs.minimum:
                continue
            members = list(cs.members)
            rng.shuffle(members)
            while self.counts[csi] < cs.minimum:
                cand = next((i for i in members if self.can_add(i)), None)
                if cand is None:
                    return False
                self.add(cand)

        # Phase 2: fill to length.
        if len(self.chosen) > p.length:
            return False
        fillers = list(range(p.n_items))
        rng.shuffle(fillers)
        for i in fillers:
            if len(self.chosen) == p.length:
                break
            if self.can_add(i):
                self.add(i)
        return len(self.chosen) == p.length
