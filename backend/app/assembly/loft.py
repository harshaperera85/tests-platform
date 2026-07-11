"""LOFT per-session assembly (BP-MODES-1 §4) — one conforming form per session.

The §4 contract, implemented behind a single call ("return a conforming form for
this session or fail loudly"):

- **Conformance = fixed-form conformance** (§4): content constraints resolved
  against ``length`` + enemy policy — the existing compiler unchanged.
- **§4.1 statistical parallelism:** when a TIF target is present its ``tolerance``
  is a **hard acceptance criterion** — a form is administrable iff
  ``|TIF(θ_k) − target_k| ≤ tolerance`` at every θ point. A target *without* a
  tolerance is rejected at binding time. Content-only LOFT is legal
  (§2.1(2)) — forms are then parallel in content only (warned).
- **§4.2 exposure:** ``max_use_per_item`` / ``max_pairwise_overlap`` are batch
  concepts — ignored with a warning. ``max_exposure_rate`` is a **running cap**:
  items with ``uses / sessions ≥ rate`` are masked from the candidate pool
  (usage state is supplied by the caller — the ledger integration point).
  ``exposure_feedback`` applies unchanged via the compiler.
- **§4.3 engines:** (a) seeded randomized feasibility search with the band
  acceptance test in the retry loop; (b) per-session CP-SAT with the band as
  hard constraints + a seeded random objective for form diversity. Same
  interface, same record.
- **§4.4 conformance record:** ``blueprint_conformant`` is true **by
  construction** — a non-conforming form raises :class:`LoftAssemblyError`
  (the session start MUST fail) and is never returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ortools.sat.python import cp_model

from app.assembly.ata_model import AtaModel
from app.assembly.blueprint_compiler import CompiledProblem, compile_blueprint
from app.assembly.objectives import add_randomized_band_objective
from app.assembly.strategies import get_assembly_strategy
from app.psychometrics.bank import ItemPool
from app.schemas.blueprint import Blueprint

LoftEngine = Literal["random_constrained", "cp_sat"]


class LoftAssemblyError(ValueError):
    """No conforming form exists / could be found — the session start fails."""


@dataclass(frozen=True)
class LoftSessionForm:
    """One conforming session form + its §4.4 conformance record."""

    item_ids: list[str]
    tif_actual: list[float]
    record: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def _binding_checks(blueprint: Blueprint) -> tuple[Blueprint, list[str]]:
    """§4.1/§4.2 binding rules; returns the per-session compile copy + warnings."""
    warnings: list[str] = []
    tgt = blueprint.statistical_target
    if tgt is not None and tgt.tolerance is None:
        raise LoftAssemblyError(
            "LOFT binding requires a tolerance on the TIF target (BP-MODES-1 "
            "§4.1: the band is the hard acceptance criterion — an objective "
            "with no acceptance band is meaningless per-session)"
        )
    if tgt is None:
        warnings.append(
            "content-only LOFT: forms are parallel in content only, not "
            "statistically (BP-MODES-1 §2.1)."
        )
    exp = blueprint.exposure_target
    updates: dict[str, Any] = {"num_forms": 1}
    if exp is not None:
        ignored = []
        if exp.max_use_per_item is not None:
            ignored.append("max_use_per_item")
        if exp.max_pairwise_overlap is not None:
            ignored.append("max_pairwise_overlap")
        if ignored:
            warnings.append(
                f"batch exposure field(s) {ignored} ignored under LOFT (§4.2: "
                "no finite batch); max_exposure_rate applies as the running cap."
            )
        # the compiler must not see batch exposure at num_forms=1; the rate is
        # enforced here as the pre-compile mask, not by the batch machinery.
        updates["exposure_target"] = None
    return blueprint.model_copy(update=updates), warnings


def _rate_mask(
    pool: ItemPool,
    rate: float | None,
    usage_counts: dict[str, int] | None,
    n_prior_sessions: int,
) -> tuple[ItemPool, int]:
    """§4.2 running cap: mask items with uses/sessions ≥ rate. Returns
    (eligible pool, n_masked)."""
    if rate is None or n_prior_sessions <= 0 or not usage_counts:
        return pool, 0
    eligible = [
        it
        for it in pool.items
        if usage_counts.get(it.item_id, 0) / n_prior_sessions < rate
    ]
    if len(eligible) == len(pool.items):
        return pool, 0
    return ItemPool(eligible, metric=pool.metric), len(pool.items) - len(eligible)


def _band_ok(problem: CompiledProblem, chosen: list[int]) -> bool:
    if not problem.target_info or problem.tolerance is None:
        return True
    tif = problem.tif_at(chosen)
    return all(
        abs(actual - target) <= problem.tolerance + 1e-9
        for actual, target in zip(tif, problem.target_info, strict=True)
    )


def _solve_random(
    problem: CompiledProblem, seed: int, max_attempts: int
) -> list[int]:
    """Engine (a): seeded random feasibility search + §4.1 acceptance retry loop."""
    strategy = get_assembly_strategy("random_constrained")
    index_of = {iid: i for i, iid in enumerate(problem.item_ids)}
    for attempt in range(max_attempts):
        result = strategy.assemble(problem, seed=seed * 100_003 + attempt)
        if not result.feasible or not result.forms:
            raise LoftAssemblyError(
                "no content-feasible form exists for this blueprint/pool "
                f"(engine=random_constrained, attempt {attempt + 1})"
            )
        chosen = [index_of[iid] for iid in result.forms[0].item_ids]
        if _band_ok(problem, chosen):
            return chosen
    raise LoftAssemblyError(
        f"no form satisfied the TIF tolerance band in {max_attempts} attempts "
        "(engine=random_constrained) — widen the tolerance, adjust the target, "
        "or use the cp_sat engine (band as hard constraints)"
    )


def _solve_cp_sat(
    problem: CompiledProblem, seed: int, time_limit_s: float
) -> list[int]:
    """Engine (b): per-session CP-SAT — band hard, randomized objective."""
    am = AtaModel(problem)
    add_randomized_band_objective(am, seed)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.random_seed = seed % (2**31 - 1)
    # single worker: per-session solves are small, and parallel portfolio races
    # break exact seed-reproducibility (lane convention C5)
    solver.parameters.num_search_workers = 1
    status = solver.solve(am.model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise LoftAssemblyError(
            "no form satisfies the content constraints + TIF band "
            "(engine=cp_sat) — the blueprint/pool pairing is infeasible for LOFT"
        )
    chosen = [
        i for i in range(problem.n_items) if solver.value(am.x[(i, 0)]) == 1
    ]
    if not _band_ok(problem, chosen):  # pragma: no cover - band is hard in-model
        raise LoftAssemblyError("cp_sat solution violated the band (internal)")
    return chosen


def assemble_loft_session(
    blueprint: Blueprint,
    pool: ItemPool,
    *,
    engine: LoftEngine = "random_constrained",
    seed: int = 0,
    usage_counts: dict[str, int] | None = None,
    n_prior_sessions: int = 0,
    max_attempts: int = 60,
    time_limit_s: float = 5.0,
    exposure_counts: dict[str, int] | None = None,
) -> LoftSessionForm:
    """Return one conforming form for this session, or raise loudly (§4.3).

    ``usage_counts``/``n_prior_sessions`` feed the §4.2 running exposure-rate
    mask (the ledger integration point — live per-administration recording
    arrives with Sessions). ``exposure_counts`` is the unchanged
    ``exposure_feedback`` input (compiler-owned, §4.2 last bullet).
    """
    session_bp, warnings = _binding_checks(blueprint)
    rate = (
        blueprint.exposure_target.max_exposure_rate
        if blueprint.exposure_target is not None
        else None
    )
    masked_pool, n_masked = _rate_mask(pool, rate, usage_counts, n_prior_sessions)
    if n_masked:
        warnings.append(
            f"exposure-rate cap masked {n_masked} item(s) at "
            f"rate ≥ {rate} over {n_prior_sessions} session(s)."
        )

    problem = compile_blueprint(
        session_bp, masked_pool, exposure_counts=exposure_counts
    )
    warnings.extend(problem.warnings)

    if engine == "cp_sat":
        chosen = _solve_cp_sat(problem, seed, time_limit_s)
    else:
        chosen = _solve_random(problem, seed, max_attempts)

    tif_actual = problem.tif_at(chosen)
    constraints = []
    for cs in problem.content_sets:
        realized = sum(1 for i in chosen if i in set(cs.members))
        constraints.append(
            {
                "key": cs.key,
                "required_min": cs.minimum,
                "required_max": cs.maximum,
                "realized": realized,
                "satisfied": (cs.minimum is None or realized >= cs.minimum)
                and (cs.maximum is None or realized <= cs.maximum),
            }
        )
    if not all(c["satisfied"] for c in constraints):  # pragma: no cover
        raise LoftAssemblyError("assembled form violated a content constraint")

    record: dict[str, Any] = {
        "blueprint_conformant": True,  # by construction — failures raise
        "realized_length": len(chosen),
        "constraints": constraints,
        "tif_actual": tif_actual,
        "tif_target": list(problem.target_info),
        "tolerance": problem.tolerance,
        "engine": engine,
        "seed": seed,
    }
    return LoftSessionForm(
        item_ids=[problem.item_ids[i] for i in chosen],
        tif_actual=tif_actual,
        record=record,
        warnings=warnings,
    )
