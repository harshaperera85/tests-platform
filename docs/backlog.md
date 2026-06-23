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
- **CAT platform endpoints** → Phase 2 on-ramp. **Org repo (`outsmart-college`).**
  *Trigger:* committing to Phase 2 **and** ready for org involvement (note: repos move to
  `outsmart-college` only at v1-finalized). To pin, need: OpenAPI / endpoint shapes
  (start-session → next-item → respond → score → stop), the CAT `TestConfig` schema, the
  θ scaling it returns, and auth.

### Phase 2 — CAT adapter (later)
`CatStrategy` as a thin adapter to the existing CAT platform (preserve selection,
estimation, stopping incl. SPRT, exposure, content balancing, pre-CAT, neural fusion).
Depends on the Tier 3 CAT seam.

## Hardening targets (Phase 3)

### Self-contained (doable now, no external deps)
- **Audit log** — append-only `audit_event` for config/assemble/lock actions (plan §8).
- **Observability** — structured logging + request IDs; readiness probe that actually
  checks Postgres + Redis; basic metrics.
- **Job robustness** — surface assembly failures in the UI; RQ timeouts / retry / failed-job
  registry visibility; status for long-running solves.
- **Regression/contract tests** — golden-fixture assembly determinism; run integration
  tests against Postgres in CI (today they use SQLite); keep the oracle-parity gate.
- **Frontend tests** — a few Vitest/RTL component tests; error boundaries; a11y pass.
- **Security (pre-prod)** — authN/authZ (none yet); production CORS/origin handling (today a
  Vite dev proxy); secrets management; rate limiting.
- **DB** — review indexes; test migration up/down in CI; connection-pool sizing.

### Depends on seams (Tier 3 / Phase 2 / Sessions)
- **Item-bank seam contract test** — after the item-factory export is pinned.
- **Sessions handoff** — the module's exit: contract + handoff of a locked form/config.
- **CAT path load test** — mirtCAT/R concurrency ceiling — after Phase 2.
- **SME / Admin review screens** (A-038..041) and a deeper lock/version/**publish** workflow
  (basic lock landed in Tier 1).
