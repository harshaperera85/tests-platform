# Tests Platform — Project Status Snapshot

Durable current-state snapshot. **Through Phase L2c.** Tip: `8b62b4e` on `main`, CI-green
(`CI` backend + frontend, scoped `oracle-parity`). Runs entirely on simulated data, no
external deps.

> Living companion to `docs/backlog.md` (roadmap/to-do). This file answers "where are we
> right now and how did we get here"; the backlog answers "what's next". CLAUDE.md remains
> the authority on golden rules and architecture; the build plan
> (`docs/tests_module_architecture_and_build_plan.md`) on detail.

## Mission (recap)
A production-worthy **Tests module**: calibrated item bank (input) → blueprint → assemble
forms/pools → configure administration model → handoff to the **Sessions** module (exit,
out of scope). v1 builds **Linear fixed-form** + **CAT (adapter)**; the architecture
*accommodates* LOFT/MST/hybrids but does not build them.

---

## Completed phases (with commit refs)

| Phase | Commit(s) | Summary |
|-------|-----------|---------|
| **Phase 0 — scaffold** | `88bbd66` | Monorepo skeleton, engine `contract.py` + `registry.py`, config union stub, docker-compose stack (postgres, redis, backend, frontend, scoring-r), FastAPI + Alembic baseline, CI. |
| **Phase 1 — linear end-to-end** | `278e034`, `99e6652` | Blueprint schema + compiler, OR-Tools CP-SAT ATA with TIF objective (minimax/maximin), dual oracle harness (Python-exhaustive + eatATA), `LinearStrategy`, assembly API. R-oracle parity gate (eatATA vs OR-Tools) wired into CI. |
| **Phase 1.5 — linear frontend + simulated data** | `1e0cfd7`, `559f5bf`, `3d6f025` | Linear test editor + form preview + walkthrough; mixed 2PL/3PL demo bank, pool catalog, scenario presets — every workflow demonstrable without real data. |
| **Phase 1.6 — IA shell** | `fdbd45f` | react-router, Test List (A-030), Test Editor tabs (Assembly/About/Scoring/History), walkthrough route. |
| **Tier 1 — server-backed `tests` resource** | `89acf9f` | CRUD, list, draft persistence, assemble, form history, lock/unlock/duplicate. |
| **Tier 2 — async assembly** | `964d2d0` | RQ worker (queued → running → done); UI polls. |
| **Hardening H1–H7** | `ad370e0`, `f078602`, `1ce16e6`, `faa7728`, `d8c29e5`, `9de80e8` | H1 observability/readiness; H2 audit log; H3 job robustness; H4 DB index; H5 determinism guards + Postgres migration CI; H6 frontend tests + ErrorBoundary; H7 security posture (CORS closed-by-default, secrets excluded, `docs/security.md`). |
| **Metric reconciliation → canonical D=1 slope-intercept** | `f9c67ad`, `f76db67` | Canonical metric = mirt-native **logistic D=1, slope-intercept `(a,d)`**. Enforced metric contract (`require_metric`, raises on undeclared). `engines/scoring-r` `/convert-difficulty` with `SE(b)` via `mirt::DeltaMethod` (mirt = single source of truth); synthetic pools route `b=−d/a` in Python with no fabricated SE. Fixtures regenerated natively; oracle parity preserved. |
| **ATA enhancements** | `c8c2c61` | Weighted minimax (weights=1 ≡ unweighted, byte-for-byte), inter-form pairwise overlap cap, rate-based exposure (`max_exposure_rate` → `max_use`), maximin UI consistency. Shared engine — available to all assembly-based models. |
| **In-UI cross-validation** | `1d3a685` | Assemble with OR-Tools, validate read-only against eatATA via the isolated `oracle-r` service. Production assembly never routes through R. |
| **L2a — form-lifecycle governance** | `d35bf2f`, `8a08f8d` | Model-agnostic state machine (`draft → content_review → psychometric_review → approved → published`, + `return_to_draft`/`withdraw`). Form past draft freezes its test from blueprint edits + re-assembly. Append-only sign-off provenance (`form_review_event` + `audit_event`); permissive role-hook stub. Per-form QA report. **Editability + test status derived from form lifecycle** — manual Lock/Unlock retired (migration 0008). |
| **L2b — cross-form comparability** | `7c3ebe2` | `POST /forms/compare`: overlaid TIF (+ common target), conditional SE, TCC/expected-score, per-θ dispersion + pass/flag summary. Design-time interchangeability evidence — **not** post-administration score equating. |
| **L2c — longitudinal item exposure** | `8063fe3` | `item_usage_event` + `services/item_exposure.py`: published forms = real exposure (recorded on publish). Opt-in `Blueprint.exposure_feedback` into assembly eligibility — **default-off, OR-Tools model byte-for-byte unchanged when absent** (oracle parity intact). Surfaced in pool viewer (`GET /pool/exposure`). |
| **Real pool importer (#9)** | — | `POST /item-bank/import` + `GET /item-bank`: pinned item-factory contract in (verbatim `instance_id`, R3 UUID tags, nullable IRT, rule-4 metric + rescaling, identity-epoch policy w/ content-hash verification), two-axis bank record + derived administrable pool registered as a first-class catalog pool (all existing consumers incl. the async worker just work). E2E: curriculum blueprint → imported items → exact allocation. Real complete data arrives post-campaign; until then shaped fixtures exercise the identical path. |
| **Analysis-module seed (calibration engine P2)** | PR #1 (`p2-analysis-module-seed` + review fixes) | External contribution from the `item-calibration` repo, reviewed + merged: `engines/scoring-r` gains `/calibrate` (joint 2PL MML-EM, canonical (a,d) + SEs + covariances, honest convergence), `/score` (EAP under fixed params), `/update-item` (fixed-a grid posterior over d — the refinement-loop workhorse; `se_b = se_d/a` exact, `kind: "posterior-fixed-a"`), `/link` (scale-linking diagnostics). One implementation (`irt_core.R`) verified by build-time selftests (recovery, exact SE map, vcov alignment, link exactness); all endpoints serialize at `digits=15` (review fix — transport-layer truncation). **scoring-r is formally the Analysis-module home** (calibration-engine ownership = tests-platform, §10 of the common-bank design). Backend wrappers/OpenAPI = follow-up (add `posterior-fixed-a` to `PoolKind` then). |
| **BP-MODES-1 §2 + §6 — delivery-mode semantics** | `b49837c`, `ab22b52`, `6e72a9f`, + | Spec `docs/blueprint-delivery-mode-semantics.md` (authored Ignite-side). §2: optional TIF target (content-only blueprint ⇒ feasibility-only fixed-form assembly, realized TIF still reported), `schema_version: 2` (v1 docs stay valid), reserved `segments` (rejected). Content-only authoring UI. §6: curriculum→blueprint generator (`POST /blueprints/generate`) — item-factory unit JSON → manifest → EOC / unit-quiz blueprints, largest-remainder shares, authored cognitive profile (pinned dims `bloom_process`/`bloom_knowledge`/`timss`; no generic bloom, no DOK yet), feasibility gate vs pool. **§3 is Ignite-owned** (arrives with the CAT-module merge); §4 LOFT = later phase here. |

Walkthrough expanded to full end-to-end guide (linear + governance + exposure) in `ad4eec2`.

---

## Locked architecture decisions

1. **Canonical metric = mirt-native logistic D=1, slope-intercept `(a,d)`.** Single source
   of truth in `psychometrics/`. `P = c+(1−c)σ(aθ+d)`, `I = a²(Q/P)((P−c)/(1−c))²`
   (→ `a²PQ` at c=0). **No 1.702 in computation**; normal-ogive D=1.702 is a reporting
   transform only. `(a,b=−d/a)` is the difficulty view; `SE(b)` via mirt delta-method.
2. **Enforced metric contract.** Every pool declares `{scaling_d, form, kind}` via
   `require_metric` — undeclared **raises**, no silent default. Cross-source params
   reconciled by `normalize_to_canonical` at ingest.
3. **OR-Tools owns assembly; R is a sanctioned-but-modular oracle.** Production assembly is
   Python OR-Tools (CP-SAT) only. `eatATA`/`TestDesign` (R, GPL) are **validation oracles
   only**: the `oracle-parity` CI gate and the isolated runtime read-only `oracle-r`
   cross-validation service. `oracle-r` is kept separate from the package-free mirt
   `scoring-r` so the GPL oracle stays isolated / re-firewallable. **Production assembly is
   never routed through R.**
4. **CAT = adapter, not fork.** The CAT module is a thin client to the existing CAT platform
   (mirtCAT + neural services); no CAT orchestration logic duplicated into this repo. Behind
   the `AdministrationStrategy` contract, adapter-vs-absorbed is invisible.
5. **Extensibility via the contract.** Every administration model is a module implementing
   `AdministrationStrategy`, registered via the registry. Adding/changing a model never
   edits the engine core, contract, registry, or sibling strategies — new model = new file
   in `engine/strategies/` + `@register` + a config branch + a frontend panel.
6. **Cross-model governance layer.** The unit of review/approval/publication is the
   **assembled form**; a model-agnostic lifecycle state machine
   (`services/form_lifecycle.py`) governs every form regardless of how it was assembled
   (linear/CAT/MST flow through the identical lifecycle). Governance sits *over* the
   form/test resource; the engine core / contract / registry are untouched.

---

## Deliberately deferred

- **Testlets / LOFT / MST / hybrids** — architecture accommodates them; no v1 implementation.
- **AuthN/AuthZ** — product decision required (`docs/security.md`). Role hooks
  (`content_reviewer`/`psychometrician`/`publisher`) are a **deliberate permissive stub**:
  `authorize_transition` records the claimed role and never denies. Real authz wires in at
  that single chokepoint. Gates any exposure beyond a trusted network.
- **Item-factory calibration seam** — real item bank replacing the simulated pool. Parked
  until approaching v1 / real forms needed. **Investigated read-only**
  (`docs/item_factory_seam_investigation.md`): item-factory emits a **pre-calibration** bank
  (content + tags + `enemy_of` + status; **no IRT params**). **Design captured** in
  `docs/common_item_bank_design.md` (shared bank = two-stage lifecycle; two-axis item status —
  editorial vs calibration; Linear is the field-test/calibration instrument; immutable single
  `item_id`). **Asks to item-factory** SENT as
  `outsmart-college/item-factory-source#1` and **ANSWERED 2026-07-09** (recorded in
  `item_factory_seam_investigation.md` §7): contract = **SQLite CAT-ready export**;
  R1–R3 land with the regeneration campaign; **identity epoch** = post-campaign
  (pre-epoch `instance_id`s never calibration keys; content-hash verification);
  R7 `n_dimensions` in days. Calibration-engine ownership still open. Real pool
  importer now buildable against the pinned contract. Open: a downstream **calibration-engine** (field responses → mirt → write-back) — owner
  TBD (`common_item_bank_design.md` §10). All design-only; **nothing built, nothing unparked**.
- **CAT platform endpoint seam** — Phase 2 on-ramp (org repo). Parked until committing to
  Phase 2 + ready for org involvement. To pin: endpoint shapes
  (start-session → next-item → respond → score → stop), CAT `TestConfig` schema, θ scaling,
  auth.
- **Robust + chance-constrained ATA objectives** — shared-engine assembly objectives.
  Deferred not for architectural reasons but because they need item-parameter uncertainty
  (calibration covariance/SEs), which depends on the item-factory seam. (NB: do **not** add
  CAT exposure methods — Sympson-Hetter, randomesque — to the linear path; those are
  administration-time/CAT-only.)
- **Operational walkthrough validation** — hands-on run of the full path on simulated data
  per `docs/walkthroughs/phase1_linear_walkthrough.md`, logging bugs vs. cosmetics. Pending.

---

## Immediate next steps

1. **Drive the operational walkthrough** — validate the linear + governance + exposure path
   end-to-end on simulated data; triage findings (bugs vs. cosmetics) into the walkthrough
   table / backlog. This is the unblocked, in-scope next move.
2. **Pin Phase 2 seams** — when a real trigger arrives, pin the item-factory export contract
   and the CAT platform endpoints (deliberate decision to engage the external/org seams).
3. **CAT adapter (Phase 2)** — `CatStrategy` as a thin adapter to the existing CAT platform
   (preserve selection, estimation, stopping incl. SPRT, exposure, content balancing,
   pre-CAT, neural fusion). Blocked on the CAT endpoint seam.
