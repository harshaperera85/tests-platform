# Tests Platform — Backlog & Roadmap

Durable to-do list. Status as of the latest commit on `main`.

## Done
- **Phase 0** — scaffold (engine contract + registry, config union, docker-compose, CI).
- **Phase 1** — linear end-to-end: blueprint schema + compiler, OR-Tools ATA with TIF
  objective (minimax/maximin), dual oracle harness (exhaustive + eatATA), LinearStrategy,
  assembly API.
- **Phase 1.5** — linear frontend + **simulated-data capability** (mixed 2PL/3PL demo
  bank, pool catalog, scenario presets) so every workflow is demonstrable without real data.
- **Phase 1.6** — IA shell: react-router, Test List (A-030), Test Editor tabs
  (Assembly/About/Scoring/History), walkthrough route.
- **Tier 1** — server-backed `tests` resource (CRUD, list, draft persistence, assemble,
  form history, lock/unlock/duplicate).
- **Tier 2** — async assembly via RQ worker (queued → running → done; UI polls).
- **Hardening H1–H7** — observability/readiness, audit log, job robustness, DB index +
  Postgres migration CI, determinism guards, frontend tests + ErrorBoundary, security
  posture (CORS/secrets; auth flagged).
- **Blueprint constraints** — cross-classified cells (content × cognitive, AND of tags)
  alongside marginals; per-constraint **count or proportion**. Read-only **item-pool
  viewer** (`/pool`).
- CI green (`CI` + scoped `oracle-parity`). Runs entirely on simulated data, no external deps.

## Next up
- **Operational walkthrough** — hands-on validation of the linear path on simulated data.
  Guide: `docs/walkthroughs/phase1_linear_walkthrough.md`. Log findings in its table;
  triage bugs vs. cosmetics.

## Parked

### Tier 3 — pin external seams `[pin against repo]` — PARKED
Revisit when a real trigger arrives; **not blocking** current build (simulated data covers
all paths, and the architecture is already seam-ready: the pool catalog is the item-data
swap point, `CatConfig` + the strategy registry are the CAT slot).
- **Item-factory export contract** → real calibrated item bank (replaces simulated pool).
  Personal repo, **org-free**. *Trigger:* approaching v1 / need to assemble real forms.
  To pin, need: a real sample export + field/schema, esp. the **IRT scaling convention**
  (a on D=1 vs 1.702), tags, `enemy_of`, status, content; and how it's accessed (file/API/DB).
  - *Follow-up when pools become dynamic:* make the editor's live per-constraint
    availability flag ("N match in pool") refresh when the bank changes — invalidate the
    `getPoolItems` query on import (or set a `staleTime`/`refetchInterval`). With today's
    static fixtures it's refresh-bounded (mount / refocus / pool switch), which is fine.
- **CAT platform endpoints** → Phase 2 on-ramp. **Org repo (`outsmart-college`).**
  *Trigger:* committing to Phase 2 **and** ready for org involvement (note: repos move to
  `outsmart-college` only at v1-finalized). To pin, need: OpenAPI / endpoint shapes
  (start-session → next-item → respond → score → stop), the CAT `TestConfig` schema, the
  θ scaling it returns, and auth.

### Pinned metric fact — CAT platform = mirt 1.46.1 = **D = 1 (logistic)**
*Verified empirically* (throwaway container, R 4.4.2 + mirt 1.46.1, params passed straight
to mirt with no scaling — exactly how mirtcat-service runs):
- `iteminfo(a=1, b=0, θ=0) = 0.25` (= a²·P·Q, D=1); the D=1.702 value would be 0.724.
- `P(correct | a=1, b=0, θ=1) = 0.7310586` = `1/(1+exp(-1))` exactly; the D=1.702 value
  would be 0.8457958.
- `coef(IRTpars=TRUE)` is a slope/intercept (a1,d) → discrimination/difficulty
  (a = a1, b = -d/a1) **reparameterization only** — `a` is unchanged, so it is **not** a
  scaling constant.
So the CAT platform's θ/information are on the **D = 1** logistic scale.

### DONE — canonical metric = logistic `D = 1`, slope-intercept (mirt-native)
Two orthogonal axes, both pinned to mirt 1.46.1's native metric. **Axis 1:** logistic
`D = 1` — `P = c+(1−c)σ(aθ+d)`, `I = a²(Q/P)((P−c)/(1−c))²` (→ `a²PQ` at c=0); no 1.702
in computation; normal-ogive D=1.702 = reporting transform only. **Axis 2:**
slope-intercept `(a,d)` canonical/stored; traditional `(a,b=−d/a)` is the difficulty
view, with `SE(b)` via mirt `IRTpars=TRUE` delta-method. What shipped:
- `params.py`: native `(a,d,c,u)` `ItemParameters` (b = −d/a property; optional
  `se_a/se_d/cov_ad/se_b`); `PoolMetric{scaling_d,form,kind}` + `require_metric` (raises on
  undeclared, no silent default); `normalize_to_canonical` rescales `(a,d)` jointly.
- `information.py`: native `(a,d)` info. `reporting.py` + `display_metric_d` (presentation).
- **Fixtures regenerated natively** (seeded a,b,c; `d=−a·b`; store a,d,c,u,b; metric
  `{1.0, slope_intercept, synthetic}`); tags/enemies/stems preserved (only the embedded
  `(b=…)` annotation refreshed); `b≈−d/a` validated on load.
- **`engines/scoring-r`**: mirt 1.46.1 image + `/convert-difficulty` whose **production**
  SE(b) is computed by **`mirt::DeltaMethod`** (mirt = single source of truth). The analytic
  Jacobian is a build-time tripwire only: `convert_difficulty_selftest.R` fails the build
  unless `DeltaMethod` == `coef(IRTpars=TRUE)` == analytic (verified live: all 5 items match,
  ≠ SE(d); endpoint returns b=0.3926, se_b=0.0355 for the known case).
  `psychometrics/difficulty.py` routes synthetic (Python `b=−d/a`, no SE) vs calibrated (R svc).
- Propagated: `schemas/pool.py` (a,d,c,u,b + SE + form/kind), `/pool/items`, compiler +
  `CompiledProblem.params`, `r_oracle` payload (native a/d/g/u), frontend pool viewer (b,d).
- Tests: `test_difficulty` (delta==mirt, ≠SE(d), routing), `test_metric_contract`
  (undeclared raises, b consistency), rewritten `test_psychometrics`; determinism golden
  unchanged (tiny pool response identical under `d=−a·b`). Demo scenarios re-verified to
  assemble on the new fixtures. CLAUDE.md rule 4 + walkthrough numbers updated.
- **Oracle agreement:** Python-exhaustive ↔ MIP parity holds on the native fixtures (both
  consume the same native D=1 info matrix); eatATA parity runs in the `oracle-parity` CI job.
- **Phase-2 CAT** params are native logistic D=1 slope-intercept — no conversion needed.

### Phase 2 — CAT adapter (later)
`CatStrategy` as a thin adapter to the existing CAT platform (preserve selection,
estimation, stopping incl. SPRT, exposure, content balancing, pre-CAT, neural fusion).
Depends on the Tier 3 CAT seam.

## Hardening targets (Phase 3)

### Self-contained — DONE (H1–H7)
- **H1 Observability** — structured logging + request-id middleware; `/health/ready`
  checks Postgres + Redis. ✅
- **H2 Audit log** — append-only `audit_event` for test create/assemble/lock/unlock/
  duplicate/delete; `GET /audit`. ✅
- **H3 Job robustness** — RQ `job_timeout`; `error` surfaced on the job read; editor
  distinguishes error vs infeasible vs still-running. ✅
- **H4 DB** — index review + `test.updated_at` index for the list sort. ✅
- **H5 Test depth** — golden-fixture determinism guards; CI `migrations` job runs
  alembic up/down/up on real Postgres. ✅
- **H6 Frontend tests** — Vitest + Testing Library; ErrorBoundary; `npm test` in CI. ✅
- **H7 Security posture** — CORS default-closed (opt-in `CORS_ORIGINS`); `.env` excluded
  from images; `docs/security.md` + pre-prod checklist. ✅

### Still open (mostly self-contained, lower priority)
- Full integration suite against **Postgres** in CI (today SQLite; migrations already
  run on Postgres). Basic metrics. RQ retry / failed-job registry visibility. Rate
  limiting. Dependency scanning (`pip-audit` / `npm audit`).
- **AuthN/AuthZ** — product decision required (see `docs/security.md`); gates any
  exposure beyond a trusted network.

### Depends on seams (Tier 3 / Phase 2 / Sessions)
- **Item-bank seam contract test** — after the item-factory export is pinned.
- **Sessions handoff** — the module's exit: contract + handoff of a locked form/config.
- **CAT path load test** — mirtCAT/R concurrency ceiling — after Phase 2.
- **SME / Admin review screens** (A-038..041) and a deeper lock/version/**publish**
  workflow (basic lock landed in Tier 1).

### Depends on seams (Tier 3 / Phase 2 / Sessions)
- **Item-bank seam contract test** — after the item-factory export is pinned.
- **Sessions handoff** — the module's exit: contract + handoff of a locked form/config.
- **CAT path load test** — mirtCAT/R concurrency ceiling — after Phase 2.
- **SME / Admin review screens** (A-038..041) and a deeper lock/version/**publish** workflow
  (basic lock landed in Tier 1).
