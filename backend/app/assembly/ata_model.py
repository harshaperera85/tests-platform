"""CP-SAT model construction for automated test assembly (plan §6).

Builds the structural part of the MIP — decision variables plus length, content,
enemy, and exposure constraints — from a :class:`CompiledProblem`. The TIF
objective is layered on by :mod:`app.assembly.objectives` so the objective family
(minimax / maximin / robust / chance-constrained …) is swappable without touching
the constraint builder.

CP-SAT is integer-only, so item information (a float) is scaled by
:data:`INFO_SCALE` and rounded. The scale trades precision for solver speed; 1000
keeps TIF resolution to 0.001 info units, well below psychometric noise.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from app.assembly.blueprint_compiler import CompiledProblem

#: Multiplier turning float information into CP-SAT integers.
INFO_SCALE = 1000


class AtaModel:
    """A built CP-SAT assembly model with its decision variables exposed.

    ``x[(i, f)]`` is 1 iff item ``i`` is placed in form ``f``. ``form_info[f][k]``
    is a linear expression for the realized (scaled) TIF of form ``f`` at theta
    point ``k`` — objectives constrain these.
    """

    def __init__(self, problem: CompiledProblem) -> None:
        self.problem = problem
        self.model = cp_model.CpModel()
        self.scaled_info: list[list[int]] = [
            [round(v * INFO_SCALE) for v in row] for row in problem.info
        ]
        self.scaled_target: list[int] = [
            round(v * INFO_SCALE) for v in problem.target_info
        ]
        self.x: dict[tuple[int, int], cp_model.IntVar] = {}
        self.form_info: list[list[cp_model.LinearExpr]] = []
        self._build()

    def _build(self) -> None:
        p = self.problem
        m = self.model
        n, F = p.n_items, p.num_forms

        for f in range(F):
            for i in range(n):
                self.x[(i, f)] = m.new_bool_var(f"x_{i}_{f}")

        # Length: exactly L items per form.
        for f in range(F):
            m.add(sum(self.x[(i, f)] for i in range(n)) == p.length)

        # Content: lb <= count(members) <= ub, per form.
        for f in range(F):
            for cs in p.content_sets:
                expr = sum(self.x[(i, f)] for i in cs.members)
                if cs.minimum is not None:
                    m.add(expr >= cs.minimum)
                if cs.maximum is not None:
                    m.add(expr <= cs.maximum)

        # Enemies: at most one of an enemy pair per form.
        for f in range(F):
            for i, j in p.enemy_pairs:
                m.add(self.x[(i, f)] + self.x[(j, f)] <= 1)

        # Exposure: item used in at most max_use forms across the job.
        if p.max_use_per_item is not None and F > 1:
            for i in range(n):
                m.add(sum(self.x[(i, f)] for f in range(F)) <= p.max_use_per_item)

        # Inter-form overlap: any two forms share at most max_pairwise_overlap items.
        # z_i(f,g) >= x_if + x_ig - 1 forces z=1 when item i is in both forms; the
        # cap on sum(z) then bounds the shared count (z is free to be 0 otherwise).
        if p.max_pairwise_overlap is not None and F > 1:
            for f in range(F):
                for g in range(f + 1, F):
                    z = [m.new_bool_var(f"ov_{i}_{f}_{g}") for i in range(n)]
                    for i in range(n):
                        m.add(z[i] >= self.x[(i, f)] + self.x[(i, g)] - 1)
                    m.add(sum(z) <= p.max_pairwise_overlap)

        # Realized TIF expressions (scaled) for objective use.
        for f in range(F):
            row = [
                cp_model.LinearExpr.weighted_sum(
                    [self.x[(i, f)] for i in range(n)],
                    [self.scaled_info[i][k] for i in range(n)],
                )
                for k in range(len(p.theta_points))
            ]
            self.form_info.append(row)
