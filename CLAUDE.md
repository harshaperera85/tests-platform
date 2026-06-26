# CLAUDE.md — Tests Platform

Project context for Claude Code. Read this first, every session.
**Full detail:** `docs/tests_module_architecture_and_build_plan.md` — consult it before any structural work.

## Mission
A production-worthy **Tests module** for a large testing program: from a calibrated item bank (input)
to the Sessions module (exit). It lets a developer define a blueprint, assemble forms/pools, and
configure the administration model (item selection, stopping rule, exposure, routing).

## Scope right now (v1)
- **Build:** Linear fixed-form, and CAT (via adapter to the existing CAT platform).
- **Do NOT build yet:** LOFT, MST, hybrids. They are fast-follow. The architecture must *accommodate*
  them, but no v1 implementation.

## Dev environment
Development runs on an **AWS EC2 Ubuntu instance with native Docker** (mirroring the CAT platform).
The conda env (`tests-platform`) and Claude Code run **on the instance**; the local machine is used
only for light editing + git. The full stack (`docker compose up`) runs **on the instance, never
locally**. See `SETUP.md`.

## Golden rules (do not violate)
1. **Extensibility via the contract.** Every administration model is a module implementing the
   `AdministrationStrategy` interface, registered via the registry. **Adding/changing a model must
   never edit the engine core, the contract, the registry, or sibling strategies.** New model =
   new file in `engine/strategies/` + `@register` + a config branch + a frontend config panel.
2. **Assembly is owned in Python (OR-Tools / CP-SAT).** `eatATA`/`TestDesign` (R, GPL) are
   **validation oracles only — they never build a deliverable form.** Two sanctioned roles: the
   CI parity gate (`oracle-parity`), and an **isolated runtime read-only cross-validation service**
   (`engines/oracle-r`, the `oracle-r` compose service) the UI can call on demand to compare an
   OR-Tools form against eatATA. **Production assembly is never routed through R.** Keep `oracle-r`
   a **separate** service from the package-free mirt `scoring-r` so the GPL oracle stays isolated /
   re-firewallable.
3. **CAT = adapter, not fork.** The CAT module is a thin client to the existing CAT platform
   (mirtCAT + neural services). Preserve all CAT functionality. Do not copy/duplicate CAT
   orchestration logic into this repo (avoid divergence). Behind the contract, adapter vs absorbed
   is invisible — we are on **adapter now**.
4. **One canonical θ metric = logistic `D = 1`, slope-intercept.** All IRT parameters and θ go
   through `psychometrics/` (single source of truth). The canonical metric matches mirt 1.46.1 /
   the CAT platform natively on **two orthogonal axes**:
   - **Axis 1 — scaling: logistic `D = 1`.** `P(θ) = c + (1−c)·σ(a·θ + d)`; info
     `I(θ) = a²·(Q/P)·((P−c)/(1−c))²`, reducing to `a²·P·Q` at c=0. **No 1.702 in computation**
     (verified: a=1,d=0 → info(0)=0.25, P(1)=0.731). Normal-ogive `D = 1.702` is an **optional
     reporting transform only** (`psychometrics/reporting.py`, config `display_metric_d`, default
     1.0); never relabel logistic `a` by ×1.702.
   - **Axis 2 — form: slope-intercept `(a, d)` is canonical/stored.** Traditional `(a, b)` with
     `b = −d/a` is the **difficulty view**. The form conversion is **mirt's job via
     `IRTpars=TRUE`** — empirically only `d↔b` changes, `a` and `D` are untouched. **SE(b) needs
     delta-method propagation of the (a,d) covariance** (`Var(b)=JΣJᵀ`), which mirt does and a
     `b=−d/a` shortcut does not. Routing: **synthetic** point-estimate pools may take `b=−d/a` in
     Python (and must **not** fabricate `SE(b)`); **calibrated** pools (with covariance) get
     `b`+`SE(b)` from the R/mirt service (`engines/scoring-r` `/convert-difficulty`), which uses
     **`mirt::DeltaMethod`** as the production computation — mirt is the single source of truth.
     The analytic Jacobian is kept only as a build-time parity tripwire that asserts agreement
     with `mirt::DeltaMethod` and `coef(IRTpars=TRUE)` (`convert_difficulty_selftest.R`).
   Every pool **must declare** its metric `{scaling_d, form, kind}` (`require_metric`) — undeclared
   raises, no silent default. Cross-source params are reconciled by `normalize_to_canonical` via
   `scaling_d`/`form` at ingest. **Phase-2 CAT params are native logistic D=1 slope-intercept — no
   conversion.**
5. **Contract-first.** Backend defines OpenAPI; the frontend API client is **generated** via Orval +
   Zod. Never hand-write the frontend API client.
6. **Blueprint vs selection.** The blueprint carries content constraints **and** a statistical (TIF)
   target. Linear/LOFT/MST use the assembly engine; **CAT uses runtime selection (mirtCAT), not ATA**
   (shadow-test ATA is a later option, not v1).
7. **Containerize from day one.** Everything runs in docker-compose; promotion to EC2/AWS is config,
   not a rewrite. **Never commit secrets** (.env, keys).
8. **Quality gates.** ruff + mypy clean; tests in unit/integration/contract/regression tiers must pass.
9. **Verification means BOTH CI jobs green.** Before pushing, run locally: **backend** (`ruff` +
   `mypy` + `pytest` + `docker compose up`) **AND frontend** (`npm install && npm run lint`, i.e.
   `tsc -b`). After pushing, check the *actual* workflow run with `gh run list` / `gh run view`
   (or `scripts/ci-status.sh`) and confirm **both** the `CI` workflow's backend and frontend jobs
   passed — and any path-triggered job (e.g. `oracle-parity`) — before reporting a phase complete.
   Read `GH_TOKEN` from the environment only; never print, hardcode, or commit a token value.

## Form-lifecycle governance (cross-model — Phase L2a)
The unit of review/approval/publication is the **assembled form** (the deliverable Sessions
administers); the test is the authoring container. A **model-agnostic** state machine
(`services/form_lifecycle.py`) governs every form regardless of how it was assembled
(linear/CAT/MST flow through the identical lifecycle): `draft → content_review →
psychometric_review → approved → published`, with `return_to_draft` (reject, comment required)
and `withdraw` (unpublish → **draft**: re-publishing re-runs both gates, no stale-approval
shortcut). Only valid transitions are allowed. **A form past `draft` freezes its test from
blueprint edits + re-assembly** (return to draft to unfreeze); `published` is the release state
and the eventual Sessions handoff point (Sessions out of scope). **Editability + the test's status
are DERIVED from the forms' lifecycle — single source of truth; the manual test Lock/Unlock was
retired (migration 0008).**
- **Sign-off provenance** (`form_review_event`, append-only, + `audit_event`): every transition
  records the claimed actor/role, from→to, timestamp, comment — surfaced in History/Review.
- **Role hooks are a DELIBERATE PERMISSIVE STUB.** Each gate declares a required role
  (`content_reviewer`/`psychometrician`/`publisher`), but `authorize_transition` records the
  claimed role and **never denies** — real AuthN/AuthZ wires in at that single chokepoint once
  decided (see `docs/security.md`).
- **Form-QA report** (`services/form_qa.py`, endpoint `GET /forms/{id}/qa-report`): answer key,
  key-balance, content coverage, and a psychometric summary (SE(θ)=1/√I(θ), TCC(θ)=Σ Pᵢ(θ),
  marginal reliability, actual-vs-target TIF) — all on the canonical **D=1 slope-intercept**
  metric. This is a governance layer over the form/test resource; the **engine core / contract /
  registry are untouched**.
- **Cross-form comparability / equating-evidence report (L2b)** (`services/form_comparability.py`,
  endpoint `POST /forms/compare`): over a *set* of forms, overlaid TIF (+ common target),
  conditional SE, and TCC/expected-score, with per-θ dispersion (spread/SD + divergence flag) and a
  pass/flag summary (max TIF deviation, max expected-score diff) — the across-forms evidence a
  psychometric reviewer consults *alongside* the per-form QA report. **Comparability ≠ equating:**
  this is design-time interchangeability on the IRT scale; it does **not** derive score-conversion
  tables from examinee response data (post-administration equating — downstream, out of scope).

## Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Redis + RQ, PostgreSQL.
- Assembly: OR-Tools (CP-SAT), in-process; long solves run as RQ jobs.
- CAT: adapter → existing CAT platform (mirtCAT R service + neural service).
- Scoring/IRT: mirt behind a thin R service (canonical θ); containerized.
- Frontend: React + TypeScript + Vite + Tailwind + Orval + Zod + React Query.

## Layout (target)
```
backend/app/{api,core,models,schemas,engine,assembly,psychometrics,repositories,workers,tests}
backend/app/engine/{contract.py,registry.py,strategies/{linear.py,cat.py}}
backend/app/assembly/{blueprint_compiler.py,ata_model.py,objectives.py,strategies/,oracles/}
engines/scoring-r/            # mirt scoring service (R + plumber)
frontend/src/{api,screens/tests,components}
infra/{docker-compose.yml,nginx/}
docs/tests_module_architecture_and_build_plan.md
```

## Current phase
**Phase 0 — scaffolding.** Create the monorepo skeleton, conda env is `tests-platform`, docker-compose
(postgres, redis, backend, frontend, scoring-r), FastAPI app + Alembic baseline, and the engine
`contract.py` + `registry.py`. Then Phase 1 = Linear end-to-end (incl. OR-Tools MIP + oracle harness),
then Phase 2 = CAT adapter. See the plan doc, §11 and §17.
**Immediate intent before Phase 2:** a hands-on operational walkthrough of the Linear
path as built — see [`docs/walkthroughs/phase1_linear_walkthrough.md`](docs/walkthroughs/phase1_linear_walkthrough.md).

## Seams to pin (before Phase 2; not blocking Phase 0/1)
- Item-bank export contract (item-factory `live` items + IRT params + tags + `enemy_of`).
- CAT platform session/orchestrator endpoints.
