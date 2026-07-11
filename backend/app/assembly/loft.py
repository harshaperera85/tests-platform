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
  hard constraints + a seeded random objective for form diversity;
  (c) **pre-generated form pool** (RECOMMENDED where forms must be
  human-reviewed — Luecht & Sireci 2011's preferred variant): the session
  *draws* from a supplied pool of batch-assembled forms instead of solving.
  Every candidate is re-verified against the blueprint at draw time (length,
  content, enemies, band) — a non-conforming pool form is excluded with a
  warning, never administered; the §4.2 running rate cap masks *forms*
  containing over-exposed items; selection is least-drawn-first with a seeded,
  order-independent tie-break (rotation → form rates converge to 1/K). Same
  interface, same record (plus draw provenance: ``form_id``, pool counts).
- **§4.4 conformance record:** ``blueprint_conformant`` is true **by
  construction** — a non-conforming form raises :class:`LoftAssemblyError`
  (the session start MUST fail) and is never returned.
"""

from __future__ import annotations

import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from ortools.sat.python import cp_model

from app.assembly.ata_model import AtaModel
from app.assembly.blueprint_compiler import CompiledProblem, compile_blueprint
from app.assembly.objectives import add_randomized_band_objective
from app.assembly.strategies import get_assembly_strategy
from app.psychometrics.bank import ItemPool
from app.schemas.blueprint import Blueprint

LoftEngine = Literal["random_constrained", "cp_sat", "pregenerated"]


class LoftAssemblyError(ValueError):
    """No conforming form exists / could be found — the session start fails.

    ``mask_attributed`` is the §4.2 shortfall attribution (Luecht & Sireci
    fn. 3): True when the failure is due to the running exposure mask — the
    UNMASKED pool was feasible — as opposed to an inherently infeasible
    blueprint/pool pairing.
    """

    def __init__(self, message: str, *, mask_attributed: bool = False) -> None:
        super().__init__(message)
        self.mask_attributed = mask_attributed


@dataclass(frozen=True)
class LoftSessionForm:
    """One conforming session form + its §4.4 conformance record."""

    item_ids: list[str]
    tif_actual: list[float]
    record: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PoolFormRef:
    """One candidate form in an engine-(c) pre-generated pool."""

    form_id: str
    item_ids: tuple[str, ...]


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


def _over_exposed_ids(
    rate: float | None,
    usage_counts: dict[str, int] | None,
    n_prior_sessions: int,
) -> set[str]:
    """§4.2 running cap: item ids with uses/sessions ≥ rate."""
    if rate is None or n_prior_sessions <= 0 or not usage_counts:
        return set()
    return {
        iid
        for iid, uses in usage_counts.items()
        if uses / n_prior_sessions >= rate
    }


def _rate_mask(
    pool: ItemPool,
    rate: float | None,
    usage_counts: dict[str, int] | None,
    n_prior_sessions: int,
) -> tuple[ItemPool, int]:
    """§4.2 running cap: mask items with uses/sessions ≥ rate. Returns
    (eligible pool, n_masked)."""
    over = _over_exposed_ids(rate, usage_counts, n_prior_sessions)
    eligible = [it for it in pool.items if it.item_id not in over]
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


def _form_violation(problem: CompiledProblem, chosen: list[int]) -> str | None:
    """Full §4 conformance re-check for a pre-generated candidate: length,
    content sets, enemies, band. Returns the first violation, or None."""
    if len(set(chosen)) != problem.length:
        return f"length {len(set(chosen))} ≠ blueprint length {problem.length}"
    chosen_set = set(chosen)
    for cs in problem.content_sets:
        realized = len(chosen_set & set(cs.members))
        if cs.minimum is not None and realized < cs.minimum:
            return f"content {cs.key!r}: {realized} < min {cs.minimum}"
        if cs.maximum is not None and realized > cs.maximum:
            return f"content {cs.key!r}: {realized} > max {cs.maximum}"
    for i, j in problem.enemy_pairs:
        if i in chosen_set and j in chosen_set:
            return (
                "enemy pair both present "
                f"({problem.item_ids[i]}, {problem.item_ids[j]})"
            )
    if not _band_ok(problem, chosen):
        return "TIF outside the tolerance band"
    return None


def _draw_hash(seed: int, form_id: str) -> int:
    """Order-independent seeded tie-break (lane convention C5): depends only on
    (seed, form_id), never on draw sequence."""
    return zlib.crc32(f"{seed}:{form_id}".encode())


def _draw_pregenerated(
    problem: CompiledProblem,
    form_pool: Sequence[PoolFormRef],
    seed: int,
    over_exposed: set[str],
    draw_counts: dict[str, int] | None,
    warnings: list[str],
) -> tuple[list[int], dict[str, Any]]:
    """Engine (c): draw one conforming form from the pre-generated pool.

    Candidates are re-verified against the blueprint (never trust a stale pool),
    rate-masked at the *form* level, then selected least-drawn-first with a
    seeded tie-break — rotation drives form rates toward 1/K.
    """
    if not form_pool:
        raise LoftAssemblyError(
            "engine 'pregenerated' needs a non-empty form pool (batch-assemble "
            "forms and publish them, or supply form_pool directly)"
        )
    index_of = {iid: i for i, iid in enumerate(problem.item_ids)}

    conforming: list[tuple[PoolFormRef, list[int]]] = []
    n_nonconforming = 0
    for ref in form_pool:
        unknown = [iid for iid in ref.item_ids if iid not in index_of]
        violation: str | None
        if unknown:
            violation = f"item(s) not in pool: {unknown[:3]}"
        else:
            chosen = [index_of[iid] for iid in ref.item_ids]
            violation = _form_violation(problem, chosen)
        if violation is not None:
            n_nonconforming += 1
            if len(warnings) < 10:
                warnings.append(
                    f"pool form {ref.form_id} excluded (non-conforming: "
                    f"{violation}) — never administered (§4.3)"
                )
            continue
        conforming.append((ref, chosen))
    if not conforming:
        raise LoftAssemblyError(
            f"no conforming form in the pre-generated pool ({len(form_pool)} "
            "candidate(s), all violated the blueprint) — re-assemble the pool "
            "against the current blueprint/pool"
        )

    eligible = [
        (ref, chosen)
        for ref, chosen in conforming
        if not (set(ref.item_ids) & over_exposed)
    ]
    n_rate_masked = len(conforming) - len(eligible)
    if not eligible:
        raise LoftAssemblyError(
            f"exposure-rate cap masked every conforming pool form "
            f"({n_rate_masked}/{len(conforming)}) — the cap is below the "
            "structural floor of a finite pool (rate ≳ overlap/K); enlarge the "
            "pool or raise the cap"
        )

    counts = draw_counts or {}
    ref, chosen = min(
        eligible,
        key=lambda rc: (counts.get(rc[0].form_id, 0), _draw_hash(seed, rc[0].form_id)),
    )
    extra = {
        "form_id": ref.form_id,
        "n_pool_forms": len(form_pool),
        "n_conforming": len(conforming),
        "n_nonconforming": n_nonconforming,
        "n_rate_masked": n_rate_masked,
    }
    return chosen, extra


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
    form_pool: Sequence[PoolFormRef] | None = None,
    draw_counts: dict[str, int] | None = None,
) -> LoftSessionForm:
    """Return one conforming form for this session, or raise loudly (§4.3).

    ``usage_counts``/``n_prior_sessions`` feed the §4.2 running exposure-rate
    mask (the ledger integration point — live per-administration recording
    arrives with Sessions). ``exposure_counts`` is the unchanged
    ``exposure_feedback`` input (compiler-owned, §4.2 last bullet).
    Engine (c) additionally takes ``form_pool`` (the pre-generated candidates)
    and ``draw_counts`` (per-form draws so far, for rotation).
    """
    session_bp, warnings = _binding_checks(blueprint)
    rate = (
        blueprint.exposure_target.max_exposure_rate
        if blueprint.exposure_target is not None
        else None
    )
    if engine == "pregenerated":
        if form_pool is None:
            raise LoftAssemblyError(
                "engine 'pregenerated' requires form_pool (the batch-assembled, "
                "reviewed candidates) — there is nothing to solve per session"
            )
        # the §4.2 cap masks whole FORMS (candidates containing over-exposed
        # items), so the compile sees the full pool — forms must resolve.
        masked_pool, n_masked = pool, 0
    else:
        masked_pool, n_masked = _rate_mask(
            pool, rate, usage_counts, n_prior_sessions
        )
        if n_masked:
            warnings.append(
                f"exposure-rate cap masked {n_masked} item(s) at "
                f"rate ≥ {rate} over {n_prior_sessions} session(s)."
            )

    problem = compile_blueprint(
        session_bp, masked_pool, exposure_counts=exposure_counts
    )
    warnings.extend(problem.warnings)

    draw_extra: dict[str, Any] = {}
    if engine == "pregenerated":
        assert form_pool is not None
        over = _over_exposed_ids(rate, usage_counts, n_prior_sessions)
        chosen, draw_extra = _draw_pregenerated(
            problem, form_pool, seed, over, draw_counts, warnings
        )
        if draw_extra["n_rate_masked"]:
            warnings.append(
                f"exposure-rate cap masked {draw_extra['n_rate_masked']} pool "
                f"form(s) at rate ≥ {rate} over {n_prior_sessions} session(s)."
            )
    else:
        draw_extra = {"n_masked_items": n_masked}
        try:
            if engine == "cp_sat":
                chosen = _solve_cp_sat(problem, seed, time_limit_s)
            else:
                chosen = _solve_random(problem, seed, max_attempts)
        except LoftAssemblyError as exc:
            if n_masked == 0:
                raise
            # §4.2 shortfall attribution (Luecht & Sireci fn. 3): the mask
            # shrank the pool — was THAT the problem, or is the pairing
            # inherently infeasible? One counterfactual unmasked solve
            # (failure path only) answers it.
            full = compile_blueprint(session_bp, pool, exposure_counts=exposure_counts)
            try:
                if engine == "cp_sat":
                    _solve_cp_sat(full, seed, time_limit_s)
                else:
                    _solve_random(full, seed, max_attempts)
            except LoftAssemblyError:
                raise LoftAssemblyError(
                    f"{exc} — infeasible regardless of the exposure mask "
                    f"({n_masked} item(s) masked; the unmasked pool also fails)"
                ) from exc
            raise LoftAssemblyError(
                f"{exc} — ATTRIBUTED to the exposure-rate cap: the unmasked "
                f"pool is feasible, but the running mask removed {n_masked} "
                "item(s) (§4.2 shortfall; raise the cap, enlarge the pool, or "
                "widen the band)",
                mask_attributed=True,
            ) from exc

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
        **draw_extra,
    }
    return LoftSessionForm(
        item_ids=[problem.item_ids[i] for i in chosen],
        tif_actual=tif_actual,
        record=record,
        warnings=warnings,
    )
