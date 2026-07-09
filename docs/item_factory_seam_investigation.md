# item-factory-source — Seam Investigation Report

Read-only investigation of the **separate** `item-factory-source` repo, captured for
tests-platform reference (the **common item-bank dataset** design and the Tier-3
item-factory export seam). The repo was cloned ephemerally, read, and deleted — nothing
from it lives in this repo. This file is the durable record of findings.

- **Date:** 2026-06-29
- **Source:** `https://github.com/outsmart-college/item-factory-source` (private, org-owned; Python; ~3.9 MB)
- **HEAD investigated:** `5c3a0a6` — *"Phase 0: wall-clock timeout guard on solver execution (#47)"* (branch `main`)
- **Scope:** investigation only; no changes made to either repo.

> File-path citations below refer to paths **inside item-factory-source**, not this repo.

---

## 0. What this system is

**Item Factory v4** — a hybrid template + LLM **automatic item generation (AIG)** pipeline
for high-stakes assessment (`README.md`). Domain-agnostic, YAML-configured. It produces a
*pre-calibration* item bank: authored, structurally validated, multi-agent-reviewed items
with full provenance, content/cognitive tags, enemy relationships, and a status lifecycle —
**but no IRT parameters** (those come downstream, from pilot administration). It is the
*authoring source* upstream of both the Linear (tests-platform) and CAT modules.

Pipeline phases (`README.md`): Bootstrap (domain config) → Phase 0 (template engineering,
design-time, OR-Tools CP-SAT) → 1 (CP-SAT instance generation) → 1b (asset generation) →
2 (structural validation) → 3 (contextual variation) → 4 (multi-agent review, 4 raters × 3
types) → **5 (enemy detection, 3-pass)** → **6 (item-bank deposit: SQLite + JSON/CSV/CAT-ready)**.

Note: item-factory uses **OR-Tools CP-SAT** too — but for *generating item instances* from
templates, an entirely different use from tests-platform's *form assembly*. No overlap/conflict.

---

## 1. The big finding — NO IRT parameters; this is a *pre-calibration* bank

**The item-factory bank has no psychometric parameters at all** — no `a/d/b`, no `c/g`
(guessing), no `u`, no SE, no covariance, no θ. Verified three ways:

- `items` table schema (`src/item_bank/schema.sql`, 10 tables + 4 views) has **no** param /
  IRT / discrimination / difficulty columns. The `items` columns are `item_id, kc_id,
  complicator, template_id, current_version_id, status, asset_path, asset_status, created_at,
  updated_at, regeneration_reason` (`docs/item_bank_spec.md` §3.1; `src/item_bank/models.py:17-29`).
- The generated-item dataclass `ItemInstance` (`src/solver.py:70-110`) carries content/structure/
  tags but **no** psychometric fields (full schema in §3 below).
- "Calibration" in this repo means **inter-rater (review) calibration, never item IRT** — see §2.

**Where IRT parameters actually enter:** the item **status lifecycle** is the tell. Items go
`generated → … → pass → pilot → live → retired → archived` (`docs/item_bank_spec.md` §2.4). The
`pilot` state is defined as *"entered pilot/calibration testing… Performance data is being
gathered."* So IRT calibration happens **after** item-factory, during pilot/field administration —
not in this pipeline. Item-factory emits items **ready for calibration**, not calibrated items.

**Consequence for the common dataset:** the shared item bank has **two lifecycle stages**:
- **Stage A — authoring (item-factory output):** content + structure + enemies + content/cognitive
  tags + review provenance + status. *No psychometrics.*
- **Stage B — calibrated bank:** Stage A **+** IRT params `(a, d, c, u)` + SE/covariance, added
  after pilot administration & mirt calibration.

cat-platform and tests-platform both consume a **Stage-B** (calibrated) bank; item-factory
produces **Stage A**. The metric question (logistic D=1 slope-intercept) therefore **does not
arise inside item-factory** — it is established at the *calibration* step (mirt), which the
cat-platform investigation already confirmed is native logistic D=1 slope-intercept.

---

## 2. "Calibration" here = rater calibration (IRR / MFRM), not item IRT

Easy to misread, so explicit: the calibration machinery is about the **review panel**, not items.

- `src/calibration_gate.py` — *"IRR Calibration Pre-Gate"*: before Phase 4 reviews the batch, a
  sample is reviewed and **ICC(2,1) + Gwet's AC1** (inter-rater reliability) are checked against
  proceed/warn thresholds; failure classifies the disagreement and recommends prompt/rubric/model
  intervention.
- `src/mfrm.py` — Many-Facet Rasch Measurement modelling **`α[j]` = rater severity**, **`δ[j,t]` =
  rater drift**, `γ[j,s]` = rater × subgroup; `θ[i]` is "item difficulty the item demands" **as
  inferred from the panel's ordinal ratings**, *not* from examinee responses. It's a
  rater-monitoring model (DRIFT/DRF), not an IRT item calibration.
- `docs/calibration_findings_20260623.md` — a real run: the whole report is ICC/AC1 agreement on
  review sub-scales (e.g. `d3a_timss_cognitive_level` AC1=0.39 = genuine rater disagreement). No
  item parameters anywhere.

---

## 3. The actual export item schema (the CAT-deployment artifact)

The real deliverable item shape is the **generated-instance dict**, `ItemInstance.to_dict()`
(`src/solver.py:70-110`):

| Field | Type | Meaning |
|---|---|---|
| `instance_id` | str | stable item id |
| `template_id` | str | canonical `{DD}_U{NN}_KC{NN}_C{NN}_T{X}` (e.g. `PA_U01_KC01_C03_TA`) — encodes domain/unit/KC/complicator/variant |
| `complicator` | int | sub-skill index within the KC |
| `radical_config` | dict | mathematical-structure variation — *"for calibration grouping"* (isomorph/clone family key) |
| `incidental_config` | dict | surface variation — *"for isomorph identification"* |
| `stem` | str | item stem (LaTeX `$…$`-delimited) |
| `key` | str | correct option letter |
| `key_value` | float\|str | correct numeric/text value |
| `distractors` | list[dict] | wrong options + rationale |
| `options_ordered` | list[str] | rendered options in display order |
| `bloom_process` | str | Bloom cognitive process (default `"Apply"`, `src/template_registry.py:68`) |
| `bloom_knowledge` | str | Bloom knowledge type (default `"Procedural"`, `:69`) |
| `misconception_sources` | list[dict] | evidence/distractor provenance |
| `enemy_of` | list[dict] | `[{enemy_id, reasons[], type}]` — see §4 |
| `layer2_context` | str | optional contextual framing (Phase 3) |
| `parametric_truth` | dict? | only for graphical items (Phase 1b) |

**Content/cognitive taxonomy** (the blueprint dimensions item-factory supplies):
- **Content hierarchy:** Domain (2-letter, `config/domain_registry.yml`: `PA` Pre-Algebra,
  `CA` College Algebra) → Unit → **KC** (knowledge component) → **Complicator** (sub-skill).
  Authored in `domains/<d>/curriculum_inventory.yml` + per-KC configs.
- **Cognitive:** **Bloom** (process + knowledge) **and** **TIMSS cognitive level**
  (`d3a`: *Knowing / Applying / Reasoning*, `docs/calibration_findings_20260623.md`).
- **Misconception sources** per item (distractor rationale / evidence tracking).

This **fills the exact gaps cat-platform's item model had.** cat-platform items lacked
`enemy_of`, `status`, and multi-tag content; item-factory has **all three** as first-class
authoring outputs.

---

## 4. Enemies, status, provenance — present and rich

- **Enemies (Phase 5, `src/enemy_detection.py`):** 3-pass detection (structural + text-similarity
  + semantic-LLM). `apply_enemy_tags()` writes each item's `enemy_of` as a **structured list**:
  `[{"enemy_id": <id>, "reasons": [...], "type": "structural"|"text"|"semantic"}]` — richer than a
  bare id list (carries reason + detection type). Self-described as *"the pipeline's deliverable;
  how these constraints are enforced during assembly is outside scope"* — i.e. explicitly handed to
  a consumer like tests-platform.
- **Status lifecycle** (`docs/item_bank_spec.md` §2): 13 states across generation/review/operational
  tracks, CHECK-constrained, with **allowed-transition enforcement** and an append-only
  `item_status_audit` trail (`from→to, actor, timestamp, reason`). The CAT delivery layer reads
  `live`-only via the `operational_items` view.
- **Full review provenance** in SQLite: per-cycle panel reports, all rater outputs + rationales,
  meta-syntheses, revisions, IRR reports, rater-drift history.

---

## 5. Consumption interface — how the export is delivered

**File-based, not an operational API.** Phase 6 (`src/pipeline.py:1131-1205`,
`phase6_save_item_bank()`) writes **two artifacts**:

1. **`item_bank.json`** — labelled in-code the **"CAT-deployment artifact."** Contains
   `self.all_instances` (the full §3 item dicts **with** `enemy_of` + Bloom + misconception +
   radical/incidental config), plus top-level `enemy_pairs` and `contextual_frames`. **This is the
   real export.**
2. **`item_bank.sqlite`** — the **"operational/diagnostic store"**: review provenance + status +
   audit (the 10-table schema). The `exporter.py` JSON/CSV/**CAT-ready** exporters read from *this*.

The FastAPI surface (`api/main.py`) is **operator/authoring-facing** (runs, domains, templates,
settings, review summaries) — there is **no operational "download calibrated item bank" endpoint**.
Consumption is by reading the emitted files (SQLite + `item_bank.json`).

### 5a. Curriculum **unit JSON** (verified 2026-07-07) — the §6 generator input

Separate from the item bank: the curriculum inventory itself is exported as **one JSON file per
unit** (`domains/<domain>/data/unit-NN-<slug>.json`; 11 files for pre_algebra at check time, all
sharing exactly one shape — no variants):

```json
{"course_id": "<uuid>", "course_name": "Pre-Algebra New",
 "unit_id": "<uuid>", "unit_order": 9, "unit_name": "Exponents",
 "knowledge_components": [
   {"id": "<uuid>", "order": 1, "name": "<KC statement>",
    "complicators": [
      {"id": "<uuid>", "order": 1, "name": "<sub-skill statement>",
       "examples": "…", "misconceptions": "…"}]}]}
```

A *course* = the set of unit files sharing `course_id`. The human-authored master list behind
these is `domains/<d>/curriculum_inventory.yml` (Units → KCs → Complicators, prose descriptions).
tests-platform's curriculum→blueprint generator (`app/schemas/generator.py`,
`services/blueprint_generator.py`, `POST /blueprints/generate`) normalizes these unit documents
into a minimal **curriculum manifest** and keys constraints on the stable `unit_id` / KC `id`
verbatim (never re-minted — the pool importer will use the same identifiers).

### 5b. Cognitive tag contract (pinned at the 2026-07-07 design review)

Cognitive tagging happens **once, in item-factory, at template-authoring time**
(`src/template_specs.py: TemplateSpec`); tests-platform treats cognitive tags as **read-only
imported item attributes** and builds no tagging/re-classification machinery. The dimensions
that actually exist on items — and therefore the only cognitive `tag_type`s tests-platform
emits or accepts:

| dimension | values |
|---|---|
| `bloom_process` | Remember, Understand, Apply, Analyze, Evaluate, Create |
| `bloom_knowledge` | Factual, Conceptual, Procedural, Metacognitive |
| `timss` | Knowing, Applying, Reasoning |

Bloom is **two-dimensional** (Anderson & Krathwohl) — never a generic `bloom` tag. **DOK is
not tagged upstream yet** — no `dok` constraints until item-factory carries it. Pool tag names
follow the `export_cat_ready()` fields (`bloom_process`, `bloom_knowledge`,
`timss_classification` → dimension `timss`, `enemy_of`) — the future input contract for the
real pool importer.

---

## 6. Internal gap found — the SQLite CAT-ready export can't carry the tags/enemies

A real **split-brain** worth flagging upstream (improvement for item-factory itself):

- The **content tags + enemies live only in `item_bank.json`** (on the `ItemInstance` dicts).
- The **SQLite `items` table has no columns** for `enemy_of`, `bloom_*`, `timss`,
  `misconception_sources`, `radical/incidental_config`, `layer2_context`.
- So `exporter.export_cat_ready()` (`src/item_bank/exporter.py`, `_cat_row()`) **hardcodes those
  fields to `None`** — with the comment *"will be sourced from item metadata once
  `phase6_save_item_bank()` is updated to write them through the repository."*

Net: the **SQLite-derived CAT-ready export is currently incomplete**; the authoritative payload is
the legacy `item_bank.json` dump. The `docs/item_bank_spec.md` migration ("replace the JSON dump
with a SQLite-backed schema") is **partially done** — review provenance migrated, but the **item
content/tag/enemy payload did not**. For item-factory to be a clean common-dataset source, those
columns (or a join table) need adding to the SQLite schema and threading through Phase 6.

---

## 7. CONTRACT RESOLUTION — item-factory's reply to issue #1 (2026-07-09)

The change-request (`docs/item_factory_change_request.md`, sent as
`outsmart-college/item-factory-source#1`) was answered in full; every claim in this report was
re-verified by the item-factory side. The pinned outcomes:

- **The export contract is the SQLite-derived CAT-ready export** (R1 accepted via option (a):
  columns + Phase-6 threading). Rationale: cumulative across runs, carries the item **status
  lifecycle** that determines administrability, and is the write-back home for calibration
  parameters. `item_bank.json` is demoted to a per-run diagnostic snapshot (non-contractual) —
  §5/§6 of this report describe the pre-fix state.
- **Identity epoch (R4, supersedes §3's stable-id assumption):** `instance_id` is currently
  `{template_id}_{selection_index}` — NOT immutable across regenerations — and a planned
  **purge + full-regeneration campaign** re-mints the whole bank. From the post-campaign epoch:
  ids globally unique + immutable, regeneration mints new ids with provenance links, and a
  **content hash** exports alongside for verification. **Pre-epoch ids must never be calibration
  join keys.**
- **R2 better than reported:** the TIMSS level is a first-class authored field on `TemplateSpec`
  (`timss_tag`, alongside `bloom_tag`) — surfacing is a stamp-through at instance generation.
- **R3 accepted verbatim:** flat tag dict `{domain, unit, kc, complicator, bloom_process,
  bloom_knowledge, timss}` with `unit`/`kc` carrying the unit-JSON UUIDs (mapped internally from
  dot-notation via `order`). No `template_id` parsing; no `dok`.
- **R6 corrected:** the per-unit JSONs are **produced by the course platform**, not item-factory
  (both repos consume them). item-factory commits to change-notice on its checked-in copies; the
  true producer belongs in any future shape conversation.
- **R7 accepted, spelling `n_dimensions`** (integer count only; dimension texts stay internal),
  omitted where no kc_config exists — matches our importer, which already accepts it. Landing:
  days. Authoring coverage of the remaining kc_configs accelerates during the campaign.
- **Timing:** R7 days; R1+R2+R3 bundled into regeneration-campaign prep (weeks, dates pinned when
  the gating recalibration is scheduled); campaign completion = the identity epoch.
- **Calibration-engine ownership: still open** (options tabled in the reply); item-factory owns
  the identity contract + a parameter **write-back schema** in its bank regardless.

## Implications for tests-platform & the common-dataset design

- **The common item bank is a two-stage lifecycle, and item-factory owns Stage A.** Authoring
  (content/structure/tags/enemies/status/provenance) is item-factory; **IRT calibration is a
  separate downstream stage** (pilot administration → mirt). The "common dataset" design must model
  both, and must not expect IRT params *from* item-factory.
- **item-factory closes the gaps cat-platform exposed.** `enemy_of` (structured, with reason+type),
  item `status` (13-state lifecycle + audit), and **multi-tag cross-classified content** (Domain/
  Unit/KC/Complicator × Bloom process+knowledge × TIMSS cognitive) are all first-class here — these
  are exactly the fields tests-platform assembly needs (content × cognitive cells, enemies, status).
- **Metric is a non-issue at this seam.** No IRT params ⇒ no D=1-vs-1.702 question, no `g`/`c` rename
  *here*. Those live at the Stage-B calibration seam (mirt), already confirmed native logistic D=1
  slope-intercept in the cat-platform report. The parked `g`↔`c` finding applies to the **calibrated**
  bank, not item-factory's output.
- **The canonical schema should be the superset across both stages**, with IRT fields **nullable /
  status-gated** (present only once `pilot`/`live` calibration data exists). A `generated`/`pass`
  item legitimately has *no* parameters; a `live` item must have them.
- **Two concrete consumption choices to make:** (a) ingest item-factory's **`item_bank.json`**
  (authoritative today) vs. the SQLite CAT-ready export (incomplete until §6 is fixed); (b) whether
  the calibrated parameters are joined onto item-factory ids **inside** item-factory (add Stage-B
  columns there) or **in tests-platform** at ingest. The §6 gap likely wants fixing upstream
  regardless.
- **`radical_config` is psychometrically meaningful**: it's the isomorph/clone-family key ("for
  calibration grouping"). Relevant to enemies, exposure, and (later) family-level calibration —
  worth carrying into the canonical schema even though Linear v1 won't use it.

> NB: investigation only. This **does not unpark** the Tier-3 item-factory seam in `docs/backlog.md`
> — it sharpens what pinning it will require. Relates to [[one-platform-common-bank]] and the
> cat-platform seam report (`docs/cat_platform_seam_investigation.md`).
