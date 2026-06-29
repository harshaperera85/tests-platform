# cat-platform — Seam Investigation Report

Read-only investigation of the **separate** `cat-platform` repo, captured for tests-platform
reference (Phase 2 CAT seam + item-bank seam). cat-platform was cloned ephemerally, read, and
deleted — nothing from it lives in this repo. This file is the durable record of findings.

- **Date:** 2026-06-28
- **Source:** `https://github.com/harshaperera85/cat-platform` (private; Python; ~613 KB)
- **HEAD investigated:** `44b5fbd` — *"Task #70: test-config editor 'Start blank' path + item-banks listing"*
- **Scope:** investigation only; no changes made to either repo.

> File-path citations below refer to paths **inside cat-platform**, not this repo.

---

## 1. Item-data format & storage

Items live in **PostgreSQL**, not flat files. Two tables (`infrastructure/postgres/init.sql`,
mirrored in `services/backend/app/models/orm.py`):

- **`item_banks`** — `item_bank_id`, `name`, `description`, `n_dimensions` (default 1),
  `latent_covariance` (JSONB, nullable), `n_items`, `is_active`, `metadata` (JSONB).
- **`items`** (`orm.py:114-141`) — the calibration payload:
  - `item_index` (int, 1-based, unique per bank — the mirt position index)
  - `itemtype` (string; CHECK: `2PL, 3PL, 4PL, graded, gpcm, nominal, partcomp`)
  - `n_categories` (nullable, for polytomous)
  - **`parameters`** — **JSONB dict of `{param_name: float}`** — IRT params live here, schema-less at the DB layer
  - `content_category` (string, nullable — single label, e.g. `"math"`)
  - presentation: `question_text`, `question_format`, `options` (JSONB), `correct_answer`
  - `metadata` (JSONB)

Pydantic mirror: `services/backend/app/schemas/item_bank.py` (`ItemBase`). Upload supports
CSV/JSON (`ItemBankUploadResponse`), but the only exercised ingestion path is the seed script (§5).

**Gaps vs. tests-platform's bank model:** no `enemy_of`/enemies, no item `status` (live/retired),
no calibration covariance/SE (`parameters` is point estimates only — `a1, d, g, u` floats, no
`se_*`/`cov_ad`), and `content_category` is a **single string**, not multi-tag/cross-classified.

## 2. Parameterization & metric — confirmed mirt-native logistic D=1, slope-intercept

**Matches tests-platform's canonical metric exactly, on both axes.** Evidence:

- **Field names are mirt-native slope-intercept:** `parameters = {"a1": <slope>, "d": <intercept>,
  "g": <guessing>, "u": <upper>}`. Seen in seed bank + generator: `{"a1": float(a), "d": float(-a*b)}`
  (`scripts/generate_item_bank.py:19,35`; `scripts/seed_database.py:199-200`).
- **`d = −a·b`** documented as the convention: *"Parameter conventions follow mirt's
  parameterization (slope-intercept form, not the older a-b form). The conversion from b to d is:
  `d = -a * b`"* (`docs/psychometric-notes.md:19-21`).
- **No scaling constant (no 1.702):** Python Fisher-info computes `P = sigmoid(a·θ + d)` and
  `I₂ₚₗ = a²·P·(1−P)` (`services/backend/app/services/cat_orchestrator.py:81-84`) — pure logistic
  D=1. 3PL/4PL extend with `g`/`u` the same way.
- **mirt is source of truth at runtime:** params pass **verbatim** into
  `mirt::generate.mirt_object(parameters=params_df, itemtype=...)` (`services/mirtcat-service/api.R:82-97`)
  — mirt's native slope-intercept ingestion, no rescaling anywhere.

**Conclusion: no θ/param conversion needed across the seam.** Field-name note: cat-platform uses
`g` for the guessing/lower asymptote where tests-platform's `ItemParameters` uses `c` (cat-platform's
own 3PL info reads `c = params.get("g")`). That's a rename to map at the seam, not a metric difference.

## 3. Datasets / item banks shipped

Banks aren't committed as data files — they're **generated at seed time**
(`scripts/seed_database.py:seed_item_bank`) plus one tiny test fixture. Four total:

| Bank | Source | n | itemtype | a (discrimination) | b (difficulty) | Purpose |
|------|--------|---|----------|--------------------|----------------|---------|
| **Test 2PL Bank** | `shared/fixtures/small_2pl_bank.json` | 5 | 2PL | 0.8–1.5 | hand-set | unit/integration tests |
| **Demo 2PL Bank (v1)** | seed, `seed=42` | 100 | 2PL | log-normal, clip [0.5, 3.0] | N(0, 1.2) | legacy; engine stress-test |
| **Demo 2PL Bank v2** | seed, `seed=20260601` | 200 | 2PL | peaked ~1.7, clip [0.9, 3.0] | N(0,1.5) clip ±3 | high-info; load testing |
| **Demo 2PL Bank v3** | seed, `seed=20260602` | 200 | 2PL | log-normal mean ~1.0, clip [0.3, 2.5] | N(0,1.5) clip ±3 | **headline demo bank** (realistic) |

All **unidimensional**, all **2PL**, all single `content_category` (`"math"` for v1–v3, `"test"` for
the fixture), θ-breadth ≈ b ∈ [−3, +3]. A **3PL** generator exists (`generate_3pl_bank`,
`g ~ Beta(5,17)` ≈ 0.22) but no 3PL bank is seeded. **No tags, no enemies, no polytomous data ships.**

## 4. What CAT needs from a pool

From the mirtCAT design/selection surface (`schemas/test_config.py`, `helpers/design_builder.R`):

- **Minimum viable pool:** items each with `item_index`, `itemtype`, and a mirt `parameters` dict.
  That alone supports the default config (`MI` selection, `MAP`/`EAP` estimation). Demo configs
  (`seed_database.py:366-378`): 2PL + EAP + MI, stop at `SE < 0.30`, `min_items=10`, `max_items=30`.
- **Size/breadth:** no hard minimum in code, but seed comments are explicit about practical needs —
  realistic discrimination spread and **wide difficulty coverage so a cohort at θ ∈ {−1.5, 0, +1.5}
  all get well-targeted items** (`seed_database.py:268-269`); ~200 items is the sweet spot.
  Very high-info banks (v2) make CAT converge in 1–2 items (degenerate for demos).
- **Optional structure the config *can* consume** (pool must supply matching data):
  - **Content balancing** — per-item `content` labels + target proportions (`design_builder.R:47-53`).
  - **Constraints** — `excluded`, `not_scored`, `ordered`/`unordered`/`independent` groups by
    `item_index` (`design_builder.R:67-91`).
  - **Exposure control** — Sympson-Hetter per-item rates or randomesque top-N
    (`design_builder.R:55-64`) — *administration-time, CAT-only* (matches tests-platform layer-3).
  - **Multidimensional** — `latent_means`/`latent_covariance` if `n_dimensions > 1` (unused by banks).
- Selection criteria: all 24 mirtCAT criteria enumerated (`SelectionCriterion`); MI default.

## 5. Consumption interface (ingestion + session/CAT API)

**Ingestion** is DB-direct: items written to the `items` table (seed script, or CSV/JSON upload in
`api/item_banks.py`). A test references a bank via `TestConfigurationORM.item_bank_id`. The CAT
`TestConfig` (`schemas/test_config.py:241`) is the full mirtCAT parameter surface, stored as JSONB:
`irt_model`, `estimation`, `selection`, `stopping`, `exposure`, `content_balancing`, `constraints`,
`hybrid`, `precat`.

**Pool → engine handoff (key seam shape):** at session start the backend loads items ordered by
`item_index` and passes parameters **verbatim** to the R service:
```python
# services/backend/app/api/sessions.py:247-248
item_parameters=[item.parameters for item in items],
itemtype=[item.itemtype for item in items],
```
→ `MirtCATClient.initialize_session()` (`mirtcat_client.py:38`) → R `POST /sessions/initialize`
(`api.R:68`), which `rbind`s the param dicts into a data.frame and calls
`mirt::generate.mirt_object(...)` then `mirtCAT(..., design_elements=TRUE)`.

**Session/CAT API** (R plumber service, `services/mirtcat-service/api.R`; Python wrapper
`mirtcat_client.py`). **Stateless calculator** — session state is a base64-serialized `catdesign`
cached in Redis (24h TTL) and checkpointed to Postgres (`session_checkpoints`):
- `POST /sessions/initialize` → `{next_item, theta, se, serialized_state}`
- `POST /sessions/{id}/respond` `{item_index, response}` → `{next_item, theta_irt, se_irt,
  should_stop, stop_reason, items_administered}`
- `POST /sessions/{id}/override-theta` `{theta, se}` → re-selects next item (the **hybrid
  neural-IRT** fusion hook — `θ_final = α(n)·θ_IRT + (1−α(n))·θ_NN` pushed back via
  `person$Update_thetas`; neural θ never drives selection directly, `psychometric-notes.md:86-112`)
- `GET /sessions/{id}`, `POST /sessions/{id}/restore`, `DELETE /sessions/{id}`
- Computational: `POST /sessions/{id}/criteria`, `/rank-items`, `POST /compute/estimate-theta`
  (one-shot), `POST /simulate/r-native` (batch ground-truth harness)

The Python FastAPI layer (`api/sessions.py`, `cat_orchestrator.py`) orchestrates examinee/simulee
flow; results persist to `test_sessions` / `session_events`.

---

## Implications for tests-platform

- **Metric seam is clean.** cat-platform is genuinely mirt-native logistic D=1 slope-intercept
  `(a1, d, g, u)` — exactly what CLAUDE.md rule 4 and the backlog "pinned metric fact" assert. The
  CAT-endpoint seam needs **no θ rescaling**; only a field rename (`g`↔`c`) and key mapping.
- **The CAT seam shape is now concrete:** session lifecycle is `initialize → respond →
  (override-theta) → stop`, stateless-calculator style, item pool handed over as `[{a1,d,...}]` +
  `itemtype[]` + a JSONB `TestConfig`. That's the on-ramp shape for a future `CatStrategy` adapter
  (Phase 2).
- **Item-bank seam gaps to reconcile:** cat-platform's item model has **no `enemy_of`, no item
  `status`, no calibration SE/covariance, and single-label content** — whereas tests-platform's
  assembly needs enemies, multi-tag/cross-classified content, and (for robust/chance-constrained
  objectives) covariance. If the calibrated bank ultimately flows *from* this system, those fields
  must be added upstream or supplied separately.

> NB: this confirms the parked Tier-3 seam assumptions in `docs/backlog.md` (item-factory + CAT
> endpoint seams). It does **not** unpark them — investigation only.
