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
2. **Assembly is owned in Python (OR-Tools / CP-SAT).** `TestDesign` and `eatATA` (R) are **dev-time
   validation oracles only** — never a runtime or shipped dependency. Do not route production
   assembly through R.
3. **CAT = adapter, not fork.** The CAT module is a thin client to the existing CAT platform
   (mirtCAT + neural services). Preserve all CAT functionality. Do not copy/duplicate CAT
   orchestration logic into this repo (avoid divergence). Behind the contract, adapter vs absorbed
   is invisible — we are on **adapter now**.
4. **One canonical θ metric.** All IRT parameters and θ are normalized through `psychometrics/`
   (single source of truth = the mirt scoring service). Mind the D-scaling mismatch (catR D=1 vs
   mirt D=1.702).
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

## Seams to pin (before Phase 2; not blocking Phase 0/1)
- Item-bank export contract (item-factory `live` items + IRT params + tags + `enemy_of`).
- CAT platform session/orchestrator endpoints.
