# Tests Platform

A production-worthy **Tests module** for a large-scale testing program: from a
calibrated item bank (input) to the Sessions module (exit). Define a blueprint,
assemble forms/pools, and configure the administration model (item selection,
stopping rule, exposure, routing).

> Read `CLAUDE.md` and `docs/tests_module_architecture_and_build_plan.md` first —
> they define the golden rules this codebase is built to enforce structurally.

## Status: Phase 0 — scaffolding

Monorepo skeleton, FastAPI app + health, SQLAlchemy/Alembic baseline, the engine
contract + registry, the `TestConfig` union skeleton, the dockerized stack, and
CI. No business logic yet (Linear → Phase 1, CAT adapter → Phase 2).

## Layout

```
backend/      FastAPI app, engine contract + registry, schemas, Alembic, tests
engines/
  scoring-r/  canonical θ metric service (mirt + plumber) — stub in Phase 0
frontend/     React + TS + Vite + Tailwind + Orval/Zod (generated API client)
infra/        docker-compose + nginx
docs/         architecture & build plan (canonical reference)
```

## Run the stack

```bash
cp .env.example .env                                   # optional; defaults work
docker compose -f infra/docker-compose.yml up --build
```

| Service   | URL                                                   |
|-----------|-------------------------------------------------------|
| backend   | http://localhost:8000/health · `/api/v1/health` · `/docs` |
| scoring-r | http://localhost:8001/health                          |
| frontend  | http://localhost:5173                                 |
| postgres  | localhost:5432   ·   redis: localhost:6379            |

## Backend dev (conda env `tests-platform`)

```bash
conda env create -f environment.yml      # once
conda activate tests-platform
cd backend
ruff check . && mypy app && pytest       # quality gates
uvicorn app.main:app --reload            # http://localhost:8000
```

## Adding an administration model (the extensibility guarantee)

1. Add a config branch to `backend/app/schemas/test_config.py`.
2. Add `backend/app/engine/strategies/<model>.py` implementing the six
   `AdministrationStrategy` methods; decorate with `@register`.
3. Add a frontend config panel keyed by `administration_model`.

No edits to the engine core, the contract, the registry, or sibling strategies.
