# scoring-r — canonical θ metric service

A thin R + plumber service wrapping `mirt`. It is the **single source of truth**
for the IRT parameterization and θ scale (CLAUDE.md golden rule 4); every engine
that touches θ normalizes through it (handles catR `D=1` vs mirt `D=1.702`).

**Phase 0:** stub — `GET /health` only, `mirt` not yet installed. Scoring
endpoints and the metric layer (`backend/app/psychometrics/`) arrive in Phase 1.
