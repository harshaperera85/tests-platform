"""Owned assembly engine (OR-Tools / CP-SAT) — plan §6.

Assembly is owned in Python (CLAUDE.md golden rule 2). TestDesign / eatATA (R) are
dev-time validation oracles only (see ``oracles/``), never a runtime dependency.

Public entry point: :func:`assemble`, the one call the rest of the backend (the
LinearStrategy, the assembly-job worker/endpoint) uses to turn a blueprint + pool
into selected forms via a named strategy.
"""

from __future__ import annotations

from app.assembly.blueprint_compiler import CompiledProblem, compile_blueprint
from app.assembly.result import AssemblyResult, FormSolution
from app.assembly.strategies import available_strategies, get_assembly_strategy
from app.psychometrics.bank import FieldPool, ItemPool
from app.schemas.blueprint import Blueprint


def assemble(
    blueprint: Blueprint,
    pool: ItemPool | FieldPool,
    *,
    strategy: str = "mip",
    time_limit_s: float = 10.0,
    seed: int = 0,
    num_workers: int = 8,
    exposure_counts: dict[str, int] | None = None,
) -> AssemblyResult:
    """Compile a blueprint against a pool and assemble form(s) with ``strategy``.

    ``exposure_counts`` (cumulative item usage) only matters when the blueprint sets
    ``exposure_feedback``; otherwise it is ignored and the result is unchanged.
    """
    problem = compile_blueprint(blueprint, pool, exposure_counts=exposure_counts)
    return get_assembly_strategy(strategy).assemble(
        problem, time_limit_s=time_limit_s, seed=seed, num_workers=num_workers
    )


__all__ = [
    "AssemblyResult",
    "CompiledProblem",
    "FormSolution",
    "assemble",
    "available_strategies",
    "compile_blueprint",
    "get_assembly_strategy",
]
