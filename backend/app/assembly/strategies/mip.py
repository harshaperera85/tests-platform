"""``mip`` — OR-Tools CP-SAT assembly with a TIF objective (plan §6 default).

Selects items satisfying content / enemy / length / exposure constraints while
matching the blueprint's TIF target under the chosen objective (minimax default).
This is the owned, in-house engine — none of the R packages provide these
objectives, which is precisely why assembly lives in Python (CLAUDE.md golden
rule 2).
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from app.assembly.ata_model import AtaModel
from app.assembly.blueprint_compiler import CompiledProblem
from app.assembly.objectives import add_maximin_objective, add_minimax_objective
from app.assembly.result import AssemblyResult, FormSolution
from app.assembly.strategies.base import AssemblyStrategy, register_strategy

_STATUS_MAP = {
    cp_model.OPTIMAL: "optimal",
    cp_model.FEASIBLE: "feasible",
    cp_model.INFEASIBLE: "infeasible",
    cp_model.MODEL_INVALID: "error",
    cp_model.UNKNOWN: "error",
}


@register_strategy
class MipStrategy(AssemblyStrategy):
    name = "mip"

    def assemble(
        self,
        problem: CompiledProblem,
        *,
        time_limit_s: float = 10.0,
        seed: int = 0,
    ) -> AssemblyResult:
        am = AtaModel(problem)
        objective_var, value_scale = (
            add_minimax_objective(am)
            if problem.method == "minimax"
            else add_maximin_objective(am)
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_s
        solver.parameters.num_search_workers = 8
        solver.parameters.random_seed = seed
        status = solver.solve(am.model)
        status_str = _STATUS_MAP.get(status, "error")

        result = AssemblyResult(
            strategy=self.name,
            status=status_str,  # type: ignore[arg-type]
            theta_points=list(problem.theta_points),
            target_info=list(problem.target_info),
            method=problem.method,
            solve_time_s=solver.wall_time,
            warnings=list(problem.warnings),
        )
        if status_str not in ("optimal", "feasible"):
            return result

        for f in range(problem.num_forms):
            chosen = [
                i for i in range(problem.n_items) if solver.value(am.x[(i, f)]) == 1
            ]
            result.forms.append(
                FormSolution(
                    item_ids=[problem.item_ids[i] for i in chosen],
                    tif_actual=problem.tif_at(chosen),
                )
            )
        result.objective_value = solver.value(objective_var) / value_scale
        return result
