# SETUP — Tests Platform

Run-once setup for the monorepo. Do this in your Positron terminal.

## 1. Prerequisites (install if missing)
- **conda** (Miniconda/Anaconda) — you have this.
- **Docker Desktop** with the **WSL2** backend (runs the full compose stack: postgres, redis,
  backend, frontend, scoring-r). ~16 GB+ RAM recommended.
- **Git** — you have this.
- That's it for the host. **R is NOT installed locally** — the mirt scoring service and the
  TestDesign/eatATA oracle harness run in containers. OR-Tools installs via pip in the conda env.

## 2. Create the project directory + drop in these files
Put the four scaffold files at the repo root, and the plan in `docs/`:
```
tests-platform/
  environment.yml
  .gitignore
  CLAUDE.md
  SETUP.md
  docs/tests_module_architecture_and_build_plan.md
```
```bash
mkdir tests-platform && cd tests-platform
mkdir docs
# copy environment.yml, .gitignore, CLAUDE.md, SETUP.md into ./
# copy the plan into ./docs/
```

## 3. Create the conda environment
```bash
conda env create -f environment.yml
conda activate tests-platform
```

## 4. Initialize git and push
Create an empty **private** repo on GitHub first (e.g. `tests-platform`), then:
```bash
git init
git add .
git commit -m "chore: project scaffold (env, gitignore, CLAUDE.md, plan)"
git branch -M main
git remote add origin https://github.com/<you>/tests-platform.git
git push -u origin main
```

## 5. Start the build in Claude Code (CLI)
From the repo root, launch Claude Code and paste the Phase 0 kickoff prompt below.

---

## Phase 0 kickoff prompt (paste into Claude Code)

> You are building the Tests Platform. **Read `CLAUDE.md` and
> `docs/tests_module_architecture_and_build_plan.md` first and follow them exactly** — especially the
> golden rules (strategy-contract extensibility, OR-Tools owns assembly with R packages as oracles
> only, CAT-as-adapter, one canonical θ metric, contract-first OpenAPI→Orval).
>
> **Phase 0 — scaffolding only. Do not implement Linear, CAT, or any assembly logic yet.** Deliver:
> 1. The monorepo skeleton exactly per the layout in the plan (`backend/`, `engines/scoring-r/`,
>    `frontend/`, `infra/`, `docs/`).
> 2. A FastAPI app (`backend/app/main.py`) with a health endpoint and versioned `/api/v1` router
>    mount; settings via `core/config.py` (pydantic-settings, reads `.env`); db/redis wiring in
>    `core/`.
> 3. SQLAlchemy 2 base + an Alembic baseline migration (empty/initial).
> 4. The engine foundation: `engine/contract.py` (the `AdministrationStrategy` ABC + `NextAction`,
>    `Navigation`, `TerminationDecision`, and the session-state types) and `engine/registry.py`
>    (`register` decorator + `get_strategy`). No concrete strategies yet — just the contract and an
>    empty registry, with a unit test proving registration/lookup works.
> 5. A Pydantic `TestConfig` discriminated union skeleton keyed by `administration_model` with stub
>    `LinearConfig` and `CatConfig` branches (fields can be minimal placeholders for now).
> 6. `infra/docker-compose.yml` with services: `postgres`, `redis`, `backend`, `frontend`,
>    `scoring-r` (stub R/plumber service that returns a health response). `.env.example` for config.
> 7. Frontend skeleton: Vite + React + TypeScript + Tailwind, with the Orval config wired to read the
>    backend OpenAPI (client generation can be a no-op until endpoints exist).
> 8. Tooling: ruff + mypy configs, a `pytest` setup with the test-tier folders
>    (`tests/{unit,integration,contract,regression}`), and a GitHub Actions CI workflow that runs
>    lint, type-check, and tests.
>
> Make it run: `docker compose up` should bring the stack up and the backend health endpoint should
> respond. Keep everything minimal but real — no business logic. After scaffolding, summarize what
> you created and confirm the health check passes. Then stop for review before Phase 1.
