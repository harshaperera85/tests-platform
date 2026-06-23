# Security posture

Current state and the pre-production checklist. This is a pre-v1 build intended to run
on a **trusted dev network** (EC2 + SSH tunnel), not yet exposed to untrusted clients.

## In place
- **No secrets in the repo.** `.env` / `.env.*` / `*.pem` / `*.key` are git-ignored and
  excluded from Docker images (`.dockerignore`); config comes from env vars
  (`app/core/config.py`). `.env.example` documents the keys.
- **CORS is default-closed.** No cross-origin access unless `CORS_ORIGINS` is set
  (comma-separated). Dev uses the same-origin Vite proxy, so none is needed.
- **Request correlation.** Every request gets an `X-Request-Id` (logged, echoed) for
  traceability; lifecycle actions are recorded in the append-only `audit_event` log.
- **Readiness probe** (`/api/v1/health/ready`) checks Postgres + Redis.

## Pre-production checklist (decisions + work, not yet done)
- [ ] **AuthN/AuthZ** — *product decision required* (who are the users? SSO/OIDC? roles
      for author vs. SME vs. admin?). Nothing is authenticated today. This gates any
      exposure beyond a trusted network. Tracked in `docs/backlog.md`.
- [ ] **Set `CORS_ORIGINS`** to the real SPA origin(s) when the frontend is served
      separately (today it's a dev proxy).
- [ ] **Secrets management** — inject DB/Redis creds via a secrets manager (not `.env`)
      in staging/prod.
- [ ] **Rate limiting / request limits** on the API edge.
- [ ] **TLS / reverse proxy** termination (nginx is in the stack for later).
- [ ] **Dependency scanning** in CI (e.g. `pip-audit`, `npm audit`).

> Until AuthN/AuthZ is decided and added, do not expose the API/UI outside a trusted
> network.
