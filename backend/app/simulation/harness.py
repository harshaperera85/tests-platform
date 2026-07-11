"""Measurement-simulation harness (G1) — population θ-recovery, same-engine.

**Only the examinee is simulated; everything else is the production code path**
(`docs/loft_literature_review.md` §2-G1; lane conventions C1/C3/C5):

- Form assembly calls the real services — :func:`app.assembly.assemble` for
  linear conditions, :func:`app.assembly.loft.assemble_loft_session` for LOFT
  (same compiler, same engines, same masks, same seeds).
- Responses are the only simulated element: ``u ~ Bernoulli(prob_correct(item,
  θ_true))`` via the canonical response function.
- Scoring calls :func:`app.psychometrics.scoring.eap_estimate` — the exact
  function both ``LinearStrategy.score`` and ``LoftStrategy.score`` delegate to.

**C5 seeding (order-independent, item-level paired):** each simulee's true θ
derives from ``(seed, global_index)`` and each response draw from
``(seed, global_index, item_id)`` — independent of processing order, and the
same item answered by the same simulee yields the same response in every
condition. Cross-condition comparisons are therefore paired at the item level
(the Ignite §7 "identical seeds so the comparison is paired" design).

This module is one lane: ``in_process_same_engine``. Per convention C1, if a
fast path is ever added, :func:`requires_full_engine` is the single boundary
predicate that decides what may run on it — today it returns reasons for every
study (there is nothing else to run on), and exists so the boundary has one
home from day one.
"""

from __future__ import annotations

import math
import time
import zlib
from collections import Counter
from dataclasses import dataclass, field

from app.assembly import assemble
from app.assembly.loft import LoftAssemblyError, PoolFormRef, assemble_loft_session
from app.psychometrics.bank import ItemPool
from app.psychometrics.information import prob_correct
from app.psychometrics.params import ItemParameters
from app.psychometrics.scoring import eap_estimate
from app.schemas.blueprint import Blueprint
from app.schemas.simulation import (
    Condition,
    ConditionalBin,
    ConditionResult,
    ExposureStats,
    LinearDesign,
    LoftDesign,
    OverallStats,
    PairedComparison,
    Population,
)

#: conditional-report bins: width 0.5 over −3…3 (the ATS/QA convention);
#: simulees outside the range fold into the edge bins.
_BIN_EDGES = [-3.0 + 0.5 * i for i in range(13)]


def requires_full_engine(condition: Condition) -> list[str]:
    """C1 boundary predicate — the ONE place that decides lane eligibility.

    Today every study runs on the single in-process same-engine lane, so this
    returns a reason for every condition; it exists so that if a fast lane ever
    appears, the boundary already has a single home (validator, runner, and
    report stamping all consult it).
    """
    return [f"{condition.design.kind} assembly/scoring run on production code"]


# ------------------------------------------------------------- C5 seeding
def _u01(*parts: int | str) -> float:
    """Deterministic uniform(0,1) from mixed parts — order-independent (C5)."""
    h = 2166136261
    for part in parts:
        data = str(part).encode()
        h = (h ^ zlib.crc32(data)) * 16777619 % (2**32)
    # final avalanche via crc of the running hash
    return (zlib.crc32(h.to_bytes(4, "little")) % 2**31) / 2**31


def _true_theta(pop: Population, seed: int, idx: int) -> float:
    u = _u01(seed, "theta", idx)
    if pop.distribution == "uniform":
        return pop.low + u * (pop.high - pop.low)
    # Box-Muller from two derived uniforms (guard u away from 0)
    u1 = max(_u01(seed, "theta1", idx), 1e-12)
    u2 = _u01(seed, "theta2", idx)
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return pop.mean + pop.sd * z


def _response(item: ItemParameters, theta: float, seed: int, idx: int) -> int:
    p = prob_correct(item, theta)
    return 1 if _u01(seed, "resp", idx, item.item_id) < p else 0


# ------------------------------------------------------------------ results
@dataclass
class _SessionOutcome:
    true_theta: float
    est_theta: float
    se: float
    item_ids: list[str]


@dataclass
class _ConditionRun:
    outcomes: list[_SessionOutcome] = field(default_factory=list)
    usage: Counter[str] = field(default_factory=Counter)
    forms: list[tuple[str, ...]] = field(default_factory=list)
    n_infeasible: int = 0
    solve_seconds: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _resolve_linear_form(
    design: LinearDesign,
    pool: ItemPool,
    blueprint: Blueprint | None,
    form_item_ids: list[str] | None,
    seed: int,
) -> list[str]:
    if design.form_id is not None:
        assert form_item_ids is not None
        return form_item_ids
    assert blueprint is not None
    # num_workers=1: the parallel CP-SAT portfolio returns tie-equivalent but
    # DIFFERENT optima across identical runs — fine operationally, fatal to a
    # reproducible study (C5). Single-worker search is exact given the seed.
    result = assemble(
        blueprint,
        pool,
        strategy=design.assembly_strategy,
        time_limit_s=10.0,
        seed=seed,
        num_workers=1,
    )
    if not result.feasible or not result.forms:
        raise ValueError(
            f"linear condition assembly was {result.status}; cannot simulate"
        )
    return list(result.forms[0].item_ids)


def run_condition(
    condition: Condition,
    pool: ItemPool,
    *,
    blueprint: Blueprint | None,
    form_item_ids: list[str] | None,
    population: Population,
    n_simulees: int,
    replications: int,
    seed: int,
) -> _ConditionRun:
    """Run one condition over the shared simulee population (same-engine)."""
    run = _ConditionRun()
    design = condition.design

    linear_items: list[ItemParameters] | None = None
    if isinstance(design, LinearDesign):
        ids = _resolve_linear_form(design, pool, blueprint, form_item_ids, seed)
        linear_items = pool.subset(ids)

    # engine (c): batch-assemble the pre-generated pool ONCE via the real
    # production assemble() (same-engine doctrine), then simulees draw from it.
    form_pool: list[PoolFormRef] | None = None
    draws: Counter[str] = Counter()
    if isinstance(design, LoftDesign) and design.engine == "pregenerated":
        assert blueprint is not None
        t0 = time.perf_counter()
        batch_bp = blueprint.model_copy(update={"num_forms": design.n_pool_forms})
        batch = assemble(
            batch_bp, pool, strategy="mip", time_limit_s=30.0, seed=seed,
            num_workers=1,  # C5: reproducible study (see _resolve_linear_form)
        )
        if not batch.feasible or not batch.forms:
            raise ValueError(
                f"pregenerated-pool batch assembly was {batch.status}; "
                "cannot simulate"
            )
        form_pool = [
            PoolFormRef(form_id=f"pool-form-{i:03d}", item_ids=tuple(f.item_ids))
            for i, f in enumerate(batch.forms)
        ]
        run.warnings.append(
            f"pregenerated pool: batch-assembled {len(form_pool)} forms in "
            f"{time.perf_counter() - t0:.2f} s (mip, single-worker); per-session "
            "cost below is the draw, not a solve"
        )
        n_distinct_pool = len({tuple(sorted(f.item_ids)) for f in form_pool})
        if n_distinct_pool < len(form_pool):
            run.warnings.append(
                f"pool has only {n_distinct_pool} distinct forms of "
                f"{len(form_pool)} — add exposure constraints (max_use_per_item "
                "/ max_pairwise_overlap) to the blueprint for pool diversity"
            )

    for rep in range(replications):
        for j in range(n_simulees):
            idx = rep * n_simulees + j  # global simulee index (C5)
            theta = _true_theta(population, seed, idx)

            if isinstance(design, LinearDesign):
                assert linear_items is not None
                items = linear_items
            else:
                assert blueprint is not None
                loft: LoftDesign = design
                t0 = time.perf_counter()
                try:
                    form = assemble_loft_session(
                        blueprint,
                        pool,
                        engine=loft.engine,
                        seed=seed * 1_000_003 + idx,
                        usage_counts=dict(run.usage),
                        n_prior_sessions=len(run.forms),
                        form_pool=form_pool,
                        draw_counts=dict(draws),
                    )
                except LoftAssemblyError as exc:
                    run.n_infeasible += 1
                    msg = f"session {idx}: {exc}"
                    if len(run.warnings) < 3:
                        run.warnings.append(msg)
                    continue
                run.solve_seconds.append(time.perf_counter() - t0)
                if "form_id" in form.record:
                    draws[form.record["form_id"]] += 1
                items = pool.subset(form.item_ids)
                for w in form.warnings:
                    if w not in run.warnings and len(run.warnings) < 10:
                        run.warnings.append(w)

            responses = [_response(it, theta, seed, idx) for it in items]
            est = eap_estimate(items, responses)  # the strategies' scorer
            run.outcomes.append(
                _SessionOutcome(
                    true_theta=theta,
                    est_theta=est.theta,
                    se=est.standard_error,
                    item_ids=[it.item_id for it in items],
                )
            )
            run.usage.update(it.item_id for it in items)
            run.forms.append(tuple(sorted(it.item_id for it in items)))
    return run


# --------------------------------------------------------------- statistics
def _sd(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _corr(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def summarize(run: _ConditionRun, condition: Condition) -> ConditionResult:
    out = run.outcomes
    true = [o.true_theta for o in out]
    est = [o.est_theta for o in out]
    errors = [e - t for e, t in zip(est, true, strict=True)]
    n = len(out)

    overall = OverallStats(
        n=n,
        mean_bias=sum(errors) / n if n else 0.0,
        mean_mae=sum(abs(e) for e in errors) / n if n else 0.0,
        rmse=math.sqrt(sum(e * e for e in errors) / n) if n else 0.0,
        mean_see=sum(o.se for o in out) / n if n else 0.0,
        correlation=_corr(true, est),
        reliability=_corr(true, est) ** 2,
        true_theta_sd=_sd(true),
        est_theta_sd=_sd(est),
        shrinkage_ratio=(_sd(est) / _sd(true)) if _sd(true) > 0 else 0.0,
        mean_length=sum(len(o.item_ids) for o in out) / n if n else 0.0,
    )

    # conditional on TRUE theta (the ATS convention; edges fold outliers in)
    bins: list[ConditionalBin] = []
    for k in range(len(_BIN_EDGES) - 1):
        lo, hi = _BIN_EDGES[k], _BIN_EDGES[k + 1]
        members = [
            (o, e)
            for o, e in zip(out, errors, strict=True)
            if (lo <= o.true_theta < hi)
            or (k == 0 and o.true_theta < lo)
            or (k == len(_BIN_EDGES) - 2 and o.true_theta >= hi)
        ]
        center = (lo + hi) / 2
        if not members:
            bins.append(ConditionalBin(bin_center=center, n=0))
            continue
        errs = [e for _, e in members]
        bins.append(
            ConditionalBin(
                bin_center=center,
                n=len(members),
                cbias=sum(errs) / len(errs),
                cmae=sum(abs(e) for e in errs) / len(errs),
                csee=sum(o.se for o, _ in members) / len(members),
                crmse=math.sqrt(sum(e * e for e in errs) / len(errs)),
            )
        )

    # exposure + (LOFT) overlap/diversity
    n_sessions = len(run.forms)
    rates = {
        iid: c / n_sessions for iid, c in run.usage.items()
    } if n_sessions else {}
    top_rates = dict(
        sorted(rates.items(), key=lambda kv: kv[1], reverse=True)[:200]
    )
    is_loft = condition.design.kind == "loft"
    mean_ov = max_ov = None
    n_distinct = None
    if is_loft and n_sessions >= 2:
        n_distinct = len(set(run.forms))
        # sampled pairwise overlap (deterministic sample, ≤ 1000 pairs)
        overlaps: list[float] = []
        step = max(1, (n_sessions * (n_sessions - 1) // 2) // 1000)
        pair_idx = 0
        for a in range(n_sessions):
            for b in range(a + 1, n_sessions):
                if pair_idx % step == 0:
                    fa, fb = set(run.forms[a]), set(run.forms[b])
                    overlaps.append(len(fa & fb) / max(len(fa), 1))
                pair_idx += 1
        if overlaps:
            mean_ov = sum(overlaps) / len(overlaps)
            max_ov = max(overlaps)

    exposure = ExposureStats(
        n_items_used=len(run.usage),
        max_rate=max(rates.values()) if rates else 0.0,
        mean_rate=(sum(rates.values()) / len(rates)) if rates else 0.0,
        n_distinct_forms=n_distinct,
        mean_pairwise_overlap=mean_ov,
        max_pairwise_overlap=max_ov,
        rates=top_rates,
    )

    solve = sorted(run.solve_seconds)
    return ConditionResult(
        name=condition.name,
        kind=condition.design.kind,
        overall=overall,
        conditional=bins,
        exposure=exposure,
        n_infeasible_sessions=run.n_infeasible,
        assembly_seconds_mean=(sum(solve) / len(solve)) if solve else None,
        assembly_seconds_p95=solve[int(0.95 * (len(solve) - 1))] if solve else None,
        warnings=run.warnings,
    )


def compare_paired(
    a_name: str, a: _ConditionRun, b_name: str, b: _ConditionRun
) -> PairedComparison:
    """Paired |error| comparison — valid because simulee idx ⇒ same true θ and
    item-level shared response seeds across conditions (C5)."""
    n = min(len(a.outcomes), len(b.outcomes))
    deltas = [
        abs(a.outcomes[i].est_theta - a.outcomes[i].true_theta)
        - abs(b.outcomes[i].est_theta - b.outcomes[i].true_theta)
        for i in range(n)
    ]
    mean_d = sum(deltas) / n if n else 0.0
    sd_d = _sd(deltas)
    z = p = None
    if n >= 30 and sd_d > 0:
        z = mean_d / (sd_d / math.sqrt(n))
        p = math.erfc(abs(z) / math.sqrt(2))  # two-sided normal
    def _rmse(run: _ConditionRun) -> float:
        es = [o.est_theta - o.true_theta for o in run.outcomes]
        return math.sqrt(sum(e * e for e in es) / len(es)) if es else 0.0
    return PairedComparison(
        condition_a=a_name,
        condition_b=b_name,
        n_pairs=n,
        mean_abs_error_delta=mean_d,
        rmse_a=_rmse(a),
        rmse_b=_rmse(b),
        z=z,
        p_value=p,
    )
