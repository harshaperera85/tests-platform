"""Independent exhaustive assembly oracle (DEV/TEST ONLY).

A from-scratch brute-force optimizer that shares **no** code path with the CP-SAT
engine — it enumerates every feasible form and returns the provably optimal
objective. On a small fixture this is the ground truth the owned engine's solution
is checked against (objective parity + constraint satisfaction).

Exhaustive enumeration is exponential, so it is guarded: callers must keep the
fixture tiny (``C(n, length)`` below :data:`MAX_COMBINATIONS`). For realistically
sized pools use :mod:`r_oracle` instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

from app.assembly.blueprint_compiler import CompiledProblem

MAX_COMBINATIONS = 2_000_000


class OracleTooLargeError(RuntimeError):
    """Raised when exhaustive enumeration would be intractable."""


@dataclass(frozen=True)
class OracleResult:
    status: str  # "optimal" | "infeasible"
    objective_value: float | None
    form_indices: tuple[int, ...] | None
    n_feasible: int


def _is_feasible(problem: CompiledProblem, combo: tuple[int, ...]) -> bool:
    chosen = set(combo)
    for i, j in problem.enemy_pairs:
        if i in chosen and j in chosen:
            return False
    for cs in problem.content_sets:
        count = sum(1 for i in cs.members if i in chosen)
        if cs.minimum is not None and count < cs.minimum:
            return False
        if cs.maximum is not None and count > cs.maximum:
            return False
    return True


def _objective(problem: CompiledProblem, combo: tuple[int, ...]) -> float:
    """Same objective definition as the engine, computed independently."""
    tif = problem.tif_at(list(combo))
    if problem.method == "minimax":
        return max(abs(tif[k] - problem.target_info[k]) for k in range(len(tif)))
    # maximin: worst-point information (engine maximizes this)
    return min(tif)


def exhaustive_assemble(problem: CompiledProblem) -> OracleResult:
    """Brute-force optimum over single-form assemblies. Independent of CP-SAT."""
    if problem.num_forms != 1:
        raise OracleTooLargeError("reference oracle supports single-form problems only")
    total = math.comb(problem.n_items, problem.length)
    if total > MAX_COMBINATIONS:
        raise OracleTooLargeError(
            f"C({problem.n_items}, {problem.length}) = {total} exceeds "
            f"MAX_COMBINATIONS={MAX_COMBINATIONS}; use the R oracle"
        )

    minimize = problem.method == "minimax"
    best_obj: float | None = None
    best_combo: tuple[int, ...] | None = None
    n_feasible = 0
    for combo in combinations(range(problem.n_items), problem.length):
        if not _is_feasible(problem, combo):
            continue
        n_feasible += 1
        obj = _objective(problem, combo)
        if (
            best_obj is None
            or (minimize and obj < best_obj)
            or (not minimize and obj > best_obj)
        ):
            best_obj, best_combo = obj, combo

    if best_combo is None:
        return OracleResult("infeasible", None, None, 0)
    return OracleResult("optimal", best_obj, best_combo, n_feasible)
