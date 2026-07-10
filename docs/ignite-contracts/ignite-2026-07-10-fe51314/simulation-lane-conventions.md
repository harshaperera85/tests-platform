# Simulation-Lane Conventions & Shared Verification-Report Format

**Status:** Adopted (task #105, 2026-07-10) · **Applies to:** Ignite CAT's
simulation framework now; the merged platform's verification harness after
M4. Co-designed with tests-platform (its linear/LOFT measurement-simulation
harness follows the same conventions) so merged-platform verification reads
uniformly.

---

## 1. The two lanes

| | `python_orchestrated` | `r_native` |
|---|---|---|
| What runs | The full production code path: orchestrator + mirtcat-service + neural-service, per item | mirtCAT's in-process batch loop; control never returns to the orchestrator between items |
| Valid claim types | **Any system-level claim**: hybrid fusion, blueprint enforcement, administration-time exposure policy, stopping-gate behavior, anything the orchestrator does | **Core-psychometric claims only**: selection/estimation/stopping math as implemented by mirtCAT itself |
| Speed | Production-fidelity; parallelizable (§3) | ~20× per session; the speed lane |

## 2. Conventions (normative)

**C1 — One boundary predicate.** `requires_orchestrator(config) -> reasons[]`
(`app/schemas/test_config.py`) is the ONLY place that decides whether a
config may run on the fast lane. The submission validator, the worker's
downgrade guard, and result stamping all consult it. When a feature lands
orchestrator-side, its reason is added THERE — never as a scattered check.
(History: the blueprint×r_native hole existed precisely because the guards
checked `hybrid` individually; enforcement shipped later and the guards
didn't grow.)

**C2 — Stamp every output.** Per-condition results carry `harness_mode`
(the EFFECTIVE lane, written after any downgrade) and `lane_coverage` (a
human-readable statement of what the lane did and did not exercise). A
result can never be silently over-read.

**C3 — Never port orchestrator logic into the R lane.** Fast paths must be
optimizations of the same code path, never a second implementation of the
same normative semantics (two implementations = invisible divergence; see
the `customNextItem` analysis). If the fast lane's domain becomes too small
to be useful, the remedy is parallelizing the production lane, not
duplicating logic.

**C4 — Parity is checked, not assumed.** `scripts/parity_check_lanes.py`
runs both lanes on the overlap domain (unconstrained MI CAT) and asserts
DISTRIBUTIONAL equivalence (RMSE/bias/mean-items within tolerance).
Per-simulee agreement is impossible by construction — response generation
uses different RNGs (Python vs R) — so the check is statistical, with
tolerances set at ~4 SE of the metric difference. Cadence: before any
release/merge that touches either lane, and after mirt/mirtCAT version
bumps.

**C5 — Determinism within a lane is exact.** Python-lane per-simulee RNGs
derive from `(condition_seed, simulee_index)`, independent of execution
order — so concurrent and sequential runs are bit-identical (verified:
24/24 sessions identical across sequential, concurrent, and
concurrent-with-R-replicas runs).

## 3. Parallel production lane

- `SIM_CONCURRENCY` (worker env, default 4): semaphore-bounded concurrent
  simulees, each with its own DB session and index-derived RNG.
- Throughput scales with `SIM_CONCURRENCY × min(R replicas, host cores)`.
  mirtcat-service is a stateless calculator (session state in Redis,
  deserialized per request), so it scales horizontally:
  `docker compose up -d --scale mirtcat-service=N`.
- Measured on the 2-vCPU dev box: correctness verified, speedup ~1× (no CPU
  headroom — R inference is the work). The win is real on ≥4-core hosts;
  re-measure on merged-platform hardware.

## 4. Shared verification-report format

Every verification report (Ignite CAT claims, tests-platform linear/LOFT
claims, merged-platform anything) uses:

**Header block**
```
Protocol:   <spec section being verified>
Date:       <date> · Engine: <platform> @ <commit>
Lanes:      <lane(s) used, with coverage statement each>
Seeds:      <global + per-condition> · N: <per condition>
Inputs:     <pool/blueprint/config identifiers>
Driver:     <committed script path + invocation>
```

**Acceptance table**
```
| criterion | target | result |
```
with a one-line verdict (PASS/FAIL) under it.

**Reproduction block** — the exact commands.

Reference implementations: `docs/verification/bp-cat-verification-report.md`
(Ignite, §7) and tests-platform's eatATA oracle-parity reports.

## 5. Merge-era notes

- The simulation framework (including this lane machinery) migrates
  wholesale in M4; the seam re-points from Ignite's orchestrator to the
  unified delivery interface, and `requires_orchestrator` generalizes to
  "requires the production delivery engine."
- This document travels in the contract pack; both platforms cite it as the
  single source for lane semantics and report format.
