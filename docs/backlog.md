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
- **BP-MODES-1** (spec: `docs/blueprint-delivery-mode-semantics.md`) — §2 schema
  amendments (optional TIF target ⇒ content-only blueprints w/ feasibility-only
  assembly; `schema_version: 2`; reserved `segments`), content-only authoring UI,
  and the **§6 curriculum→blueprint generator** (`POST /blueprints/generate`:
  item-factory unit JSON → manifest → blueprints; **rev. 2026-07-09 implemented**:
  §6.1 dimension-sum weights w/ median imputation + reported `imputed_fraction`
  (dimension counts not in today's export — issue #1 R7; fully-imputed = the
  degenerate complicator-count case), §6.2 test types unit_quiz/mid_course/
  end_of_course/cumulative_final w/ scope + per-complicator maxima, binding
  defaults per type w/ binding-aware cell encoding, authored cognitive profile
  per the pinned tag contract, feasibility gate vs pool). **§3 (CAT conformance enforcement) is Ignite-owned** — implemented in
  the Ignite CAT platform, arrives with the CAT-module merge; do not build it here.
  §4 (LOFT engine) BUILT — see the LOFT entry below.
- **Analysis-module seed** (PR #1 from the `item-calibration` repo, reviewed + merged) —
  `scoring-r` gains `/calibrate`, `/score`, `/update-item` (fixed-a posterior,
  `se_b = se_d/a` exact), `/link`; build-time selftests; full-precision serialization
  (review fix). scoring-r = the Analysis-module home; calibration-engine ownership =
  **tests-platform** (decided 2026-07-09). Follow-up: backend wrappers + OpenAPI +
  `posterior-fixed-a` in `PoolKind`.
- **Real pool importer (#9)** — `POST /item-bank/import` ingests the pinned
  item-factory CAT-ready contract: `instance_id` verbatim (R4), R3 flat tags w/
  UUID unit/kc join keys, structured/bare `enemy_of`, **nullable IRT** (Stage-A
  banks import as record-only), rule-4 metric enforcement + D-rescaling at ingest,
  identity-epoch policy (pre-epoch warning; content-hash-change violation reports
  on re-import). Two artifacts per bank (`bank.json` superset record +
  administrable `pool.json` derivation); the derived pool is a first-class catalog
  pool — blueprint editor, assembly (incl. async worker), QA all consume it with
  zero changes. Administrability DERIVED from both axes (editorial live ∧
  field_calibrated ∧ params). E2E-proven: curriculum-generated blueprint assembled
  a form from imported real-UUID items with exact allocation. Follow-ups: UI
  upload affordance; DB-backed bank post-campaign; field-study assembly on
  uncalibrated items (needs an info-less assembly path).
- **Field-study assembly path** — the calibration bootstrap's missing middle:
  imported banks derive a second, **content-only field pool** (`<bank>-field`,
  editorial live+pilot, NO parameters exposed — anchors flagged but numbers stay in
  the bank of record). `FieldPool` is a distinct type so parametric paths fail
  loudly instead of fabricating; the compiler accepts it only with content-only
  blueprints (pure feasibility, no info computed, no TIF reported). Assembly (both
  strategies + async worker), the generator's feasibility gate, the pool viewer
  (paramless items), and the editor all consume field pools; QA degrades to
  content-only (reliability None), tif-curve empty, simulate/compare/walkthrough
  guarded 422. E2E: mixed pilot+anchor import → generated content-only quiz →
  assembled field form. Next in the loop: administer via Sessions → responses →
  scoring-r `/calibrate` → write-back (item-factory schema pending).
- **§4 LOFT engine** (the CAT-merge-gate precondition, per cat-platform) —
  `LoftStrategy` (registered, config branch, linear-style delivery/EAP scoring) +
  `assembly/loft.py` per-session conforming assembly: §4.1 TIF tolerance band as
  HARD acceptance (target w/o tolerance rejected at binding; content-only legal w/
  notice), §4.2 batch exposure fields ignored w/ warning + `max_exposure_rate` as a
  running cap against supplied usage state (live ledger recording arrives with
  Sessions), §4.3 engines (a) seeded random search w/ acceptance retry and (b)
  per-session CP-SAT w/ band-hard + randomized diversity objective, §4.4
  conformance record true by construction (failures fail the session start).
  `POST /loft/sessions` = preview + §7-shaped verification surface (running cap
  across the batch); editor gains a LOFT-preview panel. Verified: CI-sized §7 run
  (150 sessions: 100% conformant, band held at every θ, empirical exposure ≤
  rate+ε, forms diverse) + live smoke (50 sessions, 50 distinct forms, rate 0.58
  under 0.6 cap).
- CI green (`CI` + scoped `oracle-parity`). Runs entirely on simulated data, no external deps.
- **G1 measurement-simulation harness** (2026-07-11, per
  `docs/loft_literature_review.md` §2-G1) — `POST /simulations`: N simulees ~ p(θ)
  (normal/uniform) × R replications through up to 4 named conditions (linear
  blueprint/form × assembly strategy, LOFT × engine) on one pool. **Same-engine
  doctrine: ONLY the examinee is simulated** — true θ + Bernoulli responses; form
  assembly is the real `assemble`/`assemble_loft_session`, scoring the real
  `eap_estimate`. Outputs: overall recovery (bias/MAE/RMSE/r/reliability/mean SE/
  shrinkage ratio — the Embretson EAP caution), conditional-on-true-θ bins
  (CBIAS/CMAE/CSEE/CRMSE, 0.5-wide, −3…3), exposure/overlap (distinct forms, rates,
  sampled pairwise overlap), infeasibility counts + solve-time stats
  (TestDesign's `freq_infeasible` pattern), item-level-paired condition
  comparisons (responses keyed by (seed, simulee, item_id) ⇒ paired z on |error|),
  §4-format report block. Conventions: C5 order-independent seed derivation
  (drove `num_workers` through assembly strategies — default 8 unchanged in
  production; harness pins 1 worker + seed since CP-SAT's 8-worker portfolio
  returns different tie-equivalent optima run-to-run); C1 trivially satisfied
  (single in-process lane, `requires_full_engine` predicate stubbed in). Verified:
  8 integration tests + live smoke (3 conditions × 200 simulees in 13 s: LOFT
  recovery parity with linear at RMSE ≈ 0.42, max exposure 0.5–0.6 vs 1.0,
  200 distinct forms, no significant paired MAE delta).
- **G2 LOFT engine (c): pre-generated form pool** (2026-07-11, BP-MODES-1
  §4.3(c) / lit-review G2 — Luecht & Sireci's preferred batch-in-advance
  variant: "content and measurement experts can review each form"). Composes
  existing pieces, no new machinery: batch `mip` multi-form assembly → forms
  pass the **governance lifecycle** → LOFT sessions *draw* instead of solving.
  `assemble_loft_session(engine="pregenerated", form_pool, draw_counts)`:
  every candidate is re-verified at draw time (length/content/enemies/band —
  a stale form is excluded + warned, never administered, §4.3); the §4.2
  running rate cap masks whole *forms* containing over-exposed items (all
  masked ⇒ loud structural-floor error); selection = least-drawn-first with a
  seeded order-independent tie-break (C5) ⇒ rotation drives form rates to 1/K.
  §4.4 record gains draw provenance (form_id, n_pool_forms/conforming/
  rate_masked). Surfaces: `POST /loft/sessions` (engine + `test_id` → its
  PUBLISHED forms are the pool; unpublished never drawable), `LoftConfig`/
  `LoftStrategy` (context `form_pool`/`draw_counts`), G1 harness
  (`LoftDesign.engine="pregenerated"` + `n_pool_forms`: pool batch-assembled
  ONCE by the real `assemble()`, per-simulee cost is the draw — ~0.5 ms vs a
  solve), editor LOFT-preview engine option. Verified: 7 unit + 2 API + 1
  harness tests; live smoke (5 forms assembled→published→drawn 25× with exact
  rotation [5,5,5,5,5], max item rate 0.40; study: pregen K=6 recovery parity
  with live LOFT, RMSE 0.381 vs 0.393, p=0.92, max rate 0.50 vs 0.61).
- **G3 exposure-control maturity: diagnostics + determination** (2026-07-11,
  lit-review G3 — measure BEFORE adopting). `ExposureDiagnostics` per
  simulation condition: sawtooth (running-rate amplitude over near-cap items,
  post burn-in), θ-segment-conditional exposure w/ noise-guarded hot flags
  (dev ≥ 0.15 AND 3.5×SE — the scan covers items×segments cells), overlap-rate
  > 0.20 fraction (TestDesign norm), per-person retake repeat rates
  (replications = re-sittings), per-session mask counts, and §4.2 **shortfall
  attribution**: on LOFT failure one counterfactual unmasked solve labels it
  mask-attributed vs inherently infeasible (`LoftAssemblyError.mask_attributed`,
  surfaced as `n_infeasible_mask_attributed`). Condition-name pattern widened
  ("cap 0.55", "K=6"). **Determination recorded in the review:** at ≥1.3×
  the structural floor the hard cap is fine (amplitude ≤ 0.09, decaying);
  near the floor it deadlocks (598/600 fail, all attributed) — probabilistic
  eligibility + fading DEFERRED w/ explicit triggers (cap < 1.2× floor
  needed, amplitude > 0.15, or CAT arrival). 3 new integration tests.
- **G4 TCC (expected-score) band** (2026-07-11, lit-review G4 — TestDesign
  precedent; score comparability is stronger than TIF precision comparability).
  `Blueprint.tcc_target {theta_points, target_scores, tolerance-required}` —
  a pure HARD band, no objective change (TIF remains the objective; legal
  without a TIF target = score-parallel-only, warned). TCC(θ)=Σ Pᵢ(θ) is
  linear in selection ⇒ the band rides the info machinery: `AtaModel` adds
  per-form scaled constraints (mip + LOFT cp_sat inherit; the scaled band is
  tightened by the worst-case rounding slop ceil((L+1)/2) scaled units so
  model-feasible ⇒ FLOAT-conformant — found via a live §4.1 post-check trip);
  LOFT engine (a) acceptance loop + engine (c) draw re-check via the shared
  band predicate; §4.4 record gains tcc_actual/target/tolerance. Absent ⇒
  compiled model byte-for-byte unchanged (oracle parity intact). Editor gains
  an expected-score band card. Verified: 9 unit tests + live smoke (40
  sessions/engine: cp_sat worst |TCC−target| 0.791 @ tol 0.8, random 1.496 @
  1.5; banded study 150 simulees, 150 distinct forms, 0 infeasible — RMSE
  0.470 vs ~0.42 unbanded shows the form-space cost honestly).
- **G5 small items** (2026-07-11, lit-review G5; testlets deferred — platform-
  wide, long-term). (1) **Seeded item-order randomization**: `DeliveryOptions.
  randomize_item_order` on Linear/Loft configs (default OFF = byte-identical
  delivery), keyed per (session seed, item_id) — C5 order-independent; preview
  endpoint accepts `delivery`; option-order = Sessions rendering (seed carried
  as `delivery_seed`). (2) **§4.4 record persistence**: `loft_session_record`
  append-only table (migration 0010), `persist_records` flag on POST
  /loft/sessions + GET /loft/records (Sessions will persist unconditionally).
  (3) **Pretest embedding** (ATS PRE>): `DeliveryOptions.pretest {pool_id,
  n_items}` — seeded draw (field/calibrated pool, disjoint from the form),
  seeded interleave, scoring EXCLUDES pretest (EAP over operational only);
  assembly untouched. (4) **Oracle caveat pinned** in r_oracle.py: LOFT parity
  gates compare band-feasibility, never objectives. Verified: 7 delivery unit
  tests + persistence integration test + live walk (14 delivered = 12 + 2
  pretest, 12 scored, identical order on same session id) + live persist/list.

## Next up
- **Operational walkthrough** — hands-on validation of the linear path on simulated data.
  Guide: `docs/walkthroughs/phase1_linear_walkthrough.md`. Log findings in its table;
  triage bugs vs. cosmetics. **Deliberately deferred (2026-07-08): run when ready to
  merge in the CAT platform — as the ENTRY GATE to that work (certify a clean `main`
  baseline BEFORE touching any CAT integration, so findings aren't conflated with
  merge regressions).** Until then, correctness is held by the automated gates (test
  tiers, oracle parity, contract regen, per-phase live smokes). **Guide refreshed
  2026-07-11:** now covers the full delivered surface — BP-MODES-1 (§§11–15 incl.
  LOFT engines a/b/c + §4.4 record persistence) and the G-series (§§16–18: TCC
  band, delivery options, simulation studies + exposure diagnostics) — and the
  stale manual Lock/Unlock reference was corrected to the derived-status model.
  The guide is run-ready.

## Parked

### Tier 3 — pin external seams `[pin against repo]` — PARKED
Revisit when a real trigger arrives; **not blocking** current build (simulated data covers
all paths, and the architecture is already seam-ready: the pool catalog is the item-data
swap point, `CatConfig` + the strategy registry are the CAT slot).
- **Item-factory export contract** → real item bank (replaces simulated pool). Org repo
  (`outsmart-college/item-factory-source`). *Trigger:* approaching v1 / need to assemble real forms.
  **Investigated read-only** (`docs/item_factory_seam_investigation.md`, HEAD `5c3a0a6`): it emits a
  **pre-calibration** bank (content + tags + `enemy_of` + status; **no IRT params** — "calibration"
  there = inter-rater reliability, not item IRT), file-based (`item_bank.json` authoritative; SQLite
  CAT-ready export incomplete). The IRT scaling question therefore lives at the **calibration** stage,
  not here. **Design captured** in `docs/common_item_bank_design.md` (two-axis item model:
  editorial vs calibration status; Linear-as-field-test-instrument loop; immutable single id). **Asks
  to item-factory** in `docs/item_factory_change_request.md` — **SENT as
  `outsmart-college/item-factory-source#1` and ANSWERED (2026-07-09; recorded in
  `item_factory_seam_investigation.md` §7)**: all seven asks accepted (R4
  with-changes). **Contract = the SQLite CAT-ready export**; R7 `n_dimensions` lands in
  days; R1+R2+R3 land with the **regeneration campaign** (weeks), whose completion is the
  **identity epoch** — pre-epoch `instance_id`s are NOT stable and must never be
  calibration join keys (supersedes the earlier "adopt verbatim now" note; adoption holds
  from the epoch, verified via the new content hash). Calibration-engine ownership still
  open (options tabled; item-factory owns the write-back schema regardless). **Importer
  (#9) BUILT**; real complete data arrives post-campaign. **R7 DELIVERED 2026-07-09**
  (inline `n_dimensions` in unit JSONs; catalog refreshed, kc_configs kept as fallback).
  **Field studies gated on an EXPLICIT GO SIGNAL from item-factory** (stronger than
  campaign-completion: never key field data to pre-epoch instance_ids). **CA unit JSONs
  = a course-platform data delivery** (third system), not item-factory code — direct
  that ask to the course platform. **DOK decision ANSWERED
  (2026-07-10): YES** — item-factory authors DOK in the campaign; proposed vocab
  `dok` = "1"|"2"|"3"|"4" (Webb) pending their confirmation; platform keeps
  rejecting `dok` constraints until the epoch bank ships, then the dimension joins
  the pinned contract. To pin, still need: a real sample export +
  confirmation of the asks; and the downstream **calibration-engine ownership** decision
  (`common_item_bank_design.md` §10). **Decided:** adopt `instance_id` as canonical `item_id`
  verbatim, never re-mint (single join key for parameter write-back).
  - *Follow-up when pools become dynamic:* make the editor's live per-constraint
    availability flag ("N match in pool") refresh when the bank changes — invalidate the
    `getPoolItems` query on import (or set a `staleTime`/`refetchInterval`). With today's
    static fixtures it's refresh-bounded (mount / refocus / pool switch), which is fine.
- **CAT platform endpoints** → Phase 2 on-ramp. **CONTRACT PACKS RECEIVED** (additive history — never delete old packs):
  **`ignite-2026-07-10-fe51314/` is current** — its schemas (test-config,
  blueprint-binding, item-create, session-public) SUPERSEDE the 2026-07-08 copies for
  any cross-platform validation, and it adds `simulation-lane-conventions.md`
  (co-designed; our linear/LOFT harness adopts the §4 shared verification-report
  format + conventions C1/C3 — one boundary predicate per fast path; fast paths are
  optimizations of the same code path, never reimplementations).
  `ignite-2026-07-08-e080009/` (from cat-platform @ `e080009`) carries
  the full Ignite OpenAPI snapshot (CI-gated byte-identical to live), the `TestConfig`
  schema incl. `blueprint_binding` (BP-MODES-1 §5), the item-ingest contract (tags map
  matches our pinned dims), the session surface incl. the §3.5 `blueprint_conformance`
  record, and the §7 verification report (merge-gate evidence). θ scaling already verified
  D=1 (below). **Still open:** auth story; and the `vendored-blueprint-schema.sha256`
  canonicalization recipe (ask cat-platform what exactly is hashed so drift checks work).
  Phase 2 adapter work is now unblocked on contracts — remaining gate is the walkthrough +
  the user's merge trigger.

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

### DONE — Linear ATA enhancements (shared engine, all assembly-based models)
- **Weighted minimax**: optional per-θ weights `w_k` → minimize `max_k w_k·|TIF_k−target_k|`
  (`objectives.py`); default all 1.0 reproduces the unweighted model byte-for-byte (verified:
  determinism golden unchanged). Protects fit at critical θ (height = shape; weight = where
  not to compromise). Schema `TIFTarget.weights` + per-θ UI input.
- **Inter-form pairwise overlap**: `ExposureTarget.max_pairwise_overlap` caps items shared by
  any two forms (MIP in `ata_model.py`), distinct from the per-item `max_use`. UI input.
- **Rate-based exposure**: `ExposureTarget.max_exposure_rate` (0–1) → compiler
  `max_use = ceil(rate × num_forms)` (assumes uniform form administration); raw `max_use`
  remains the override. UI input.
- **Maximin UI consistency**: target-info/tolerance/weights hidden under maximin (no target);
  preview shows achieved TIF only (no target curve/gap). (Previously these were always shown.)
- Tests: `test_ata_enhancements.py` (weights=1 ≡ unweighted, weight protects critical θ,
  overlap cap incl. disjoint, rate→max_use, validators); oracles still agree.

### Deferred — robust + chance-constrained ATA objectives
Robust ATA + chance-constrained ATA objectives — shared-engine assembly objectives (available
to all assembly-based models, not linear-specific). Deferred **not for architectural reasons**
but because they require item-parameter uncertainty (calibration covariance/SEs), which depends
on the item-factory calibration seam being wired. Build when calibrated parameters with
covariance are flowing. (NB: do NOT add CAT exposure methods — Sympson-Hetter, randomesque — to
the linear path; those are administration-time/CAT-only and don't apply to fixed-form assembly.)

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
