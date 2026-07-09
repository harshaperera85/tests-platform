# Common Item-Bank Design — one platform, one shared dataset

**Status: DESIGN / PROPOSAL (not implemented).** This is a forward-design reference for the
shared item-bank dataset that feeds every administration module. It captures decisions and a
model agreed in discussion; it does **not** describe shipped code, and it **does not unpark**
any seam in `docs/backlog.md`. Build follows only when the relevant seams are pinned.

- **Date:** 2026-06-30
- **Relates to:** `docs/item_factory_seam_investigation.md`, `docs/cat_platform_seam_investigation.md`,
  CLAUDE.md golden rule 4 (canonical metric), `docs/backlog.md` (Tier-3 seams), memory `one-platform-common-bank`.

---

## 1. Framing — one platform, many modules, one bank

This is **one test platform** with multiple **administration modules** — Linear and CAT now,
LOFT and MST as fast-follows — over a **single shared item bank**. The bank is the common
*input*; the Sessions module is the common *exit*. Each module reads the slice it needs from
the same dataset; a field a module doesn't use must not break it.

The hard design problem is that "the item bank" is not one thing produced once. It is produced
in **stages by different systems**, and an item sits in the bank for a long time in an
*incomplete* state that is nonetheless legitimate. The rest of this doc is about modelling that
honestly.

---

## 2. The core idea — two independent questions about every item

Forget state names for a moment. There are **two completely different questions** you can ask
about any item, and their answers move independently, for different reasons, decided by
different people:

- **Question 1 — "Is this a good question?"** Is it well-written, fair, correct, and has someone
  reviewed and approved it? This is the item *as a piece of writing* (the **editorial** axis).
- **Question 2 — "Do we know its numbers yet?"** Every item has statistics — chiefly **difficulty**
  and **discrimination** — that you can only learn by **giving it to real test-takers and analysing
  their answers**. This is the item *as a measuring instrument* (the **calibration** axis).

They are genuinely independent. An item can be beautifully written and approved but brand new,
with **no statistics** yet. We can have solid statistics for an item and then pull it for an
editorial problem (the statistics we measured stay true). The "good question?" answer and the
"do we have its numbers?" answer are two different facts about the same item.

**Analogy — a new car:** Question 1 = "did it pass safety inspection / is it road-legal?";
Question 2 = "have we actually driven it to measure its real fuel economy?" A car can pass
inspection before anyone measures its mpg; a car with a known great mpg can later be recalled
for a safety fault (road-legal drops, the measured mpg is unchanged).

**Why this matters here:** a **Linear field-test** is how you "drive the car to measure the
mpg" — you give approved-but-no-statistics items to a sample *in order to produce* the
statistics. **CAT cannot use an item until it has the statistics** (it selects the next item
from those numbers). So the *same* approved-uncalibrated item is **exactly what Linear
field-testing needs** and **useless to CAT**. A single `status` word cannot express
"ready for one module, not the other" — which is why we keep the two questions separate.

A single item over time:

| Moment | Good question? | Have its numbers? | Who can use it |
|---|---|---|---|
| Just generated | not reviewed | no | nobody |
| Review approves it | **yes** | no | **Linear field-test only** |
| Field study + analysis done | yes | **yes** | CAT · LOFT · MST · operational Linear |
| Later: editorial problem found | pulled for re-review | yes (still valid) | nobody, until re-approved |

The last row is the proof they're two axes: the editorial answer dropped, the numbers did not.

---

## 3. The two-stage lifecycle of the shared bank

```
   item-factory                 calibration loop (§5)                 administration
   (authoring)                                                        (consumption)
 ┌──────────────┐   approved,    ┌───────────────────────┐  numbers   ┌──────────────────┐
 │ generate +   │   no numbers   │ Linear field-test form │  written   │ CAT · LOFT · MST │
 │ review items │ ─────────────▶ │ → administer → IRT     │ ─────────▶ │ + operational    │
 │ (Stage A)    │                │ analysis (mirt)        │  back onto │ Linear (Stage B) │
 └──────────────┘                └───────────────────────┘  same id   └──────────────────┘
```

- **Stage A — authoring (item-factory output):** content + structure + enemies + content/cognitive
  tags + review provenance + editorial status. **No psychometric parameters.** (See
  `docs/item_factory_seam_investigation.md`.)
- **Stage B — calibrated bank:** Stage A **plus** IRT parameters `(a, d, c, u)` + SE/covariance,
  written back **after** field administration and IRT analysis.

The metric question (logistic **D=1 slope-intercept**, CLAUDE.md rule 4) lives **only at Stage B**
— there are no parameters at Stage A, so no metric/`g`-vs-`c`/`D`-vs-`1.702` question arises in
item-factory. The `g`↔`c` field rename (see §9) applies to the *calibrated* bank.

---

## 4. The two status axes (the model to implement)

Model the two questions as **two orthogonal, item-grain status fields**, each owned by a
different system, plus a **calibration payload**. Module eligibility is **derived**, never stored.

### Axis A — Editorial / operational lifecycle  *(owned by item-factory + review/SME)*
> `generated → in_review → {approved | rejected} ; approved → in_operation →
>  {quarantined → in_review | retired → archived}`
> Answers Question 1: *is the content sound, reviewed, and cleared for use?*

### Axis B — Calibration / psychometric status  *(owned by the calibration engine)*
> `uncalibrated → provisional → field_calibrated → operational_calibrated`,
> plus `recalibrating` and `invalidated`.
> Carries the **calibration payload**: `a, d, c, u`, `se_a/se_d/cov_ad/se_b`,
> `calibration_source` (`ai_predicted` | `field_study:<id>` | …), calibration sample / linking
> group id, date. Answers Question 2: *do we have trustworthy numbers, and from where?*

### Module eligibility is DERIVED — a function of (A, B) against per-program policy
```
linear_fieldtest_eligible   = A == approved              ∧ B ∈ {uncalibrated, provisional}
cat_eligible                = A ∈ {approved, in_operation} ∧ B == field_calibrated
loft_eligible / mst_eligible = same as cat_eligible
linear_operational_eligible = same as cat_eligible
```
*Which* (A, B) combinations a program accepts is **policy/config**, not hardcoded — a high-stakes
program forbids CAT on `provisional`; a low-stakes one may allow a warm start. The schema records
the state; the program decides the gate. **Nothing stores "CAT-ready."**

### This is already idiomatic in the codebase
- **L2a governance** retired manual Lock/Unlock and **derived** editability+status from the form
  lifecycle (migration 0008) — "single source of truth; status is DERIVED." Two-axis items are the
  same move one grain down.
- The metric **`kind: synthetic | calibrated`** in `params.py` is a two-value embryo of Axis B; we
  widen it, we don't invent it.

### Decomposing item-factory's conflated states onto the two axes
item-factory uses one axis that **fuses** the two questions in its later states (`pilot` = approved
**and** being field-calibrated; `live` silently requires calibrated). On ingest we decompose:

| item-factory `status` | → Axis A | → Axis B |
|---|---|---|
| `generated` | generated | uncalibrated |
| `under_review` / `revising` | in_review | (unchanged) |
| `pass` | **approved** | **uncalibrated** ← the state it can't cleanly name |
| `reject` / `revise_exhausted` / `regenerate_recommended` / `validation_failed` | rejected | n/a |
| `pilot` | approved | **field_study_in_progress** ← the conflation, split out |
| `live` | in_operation | **field_calibrated** ← the hidden requirement, explicit |
| `quarantined` | quarantined | *(preserved — params stay valid)* |
| `retired` / `archived` | retired / archived | *(frozen)* |

> `live` from item-factory **cannot be taken at face value** as "calibrated for our purpose" — we
> may re-calibrate on our own field study. Ingest maps states; it does not trust them blindly.

---

## 5. The calibration loop — Linear is the instrument

The two-axis model implies a stage that does not exist yet: **field administration → IRT analysis →
write parameters back onto the same item.**

- **Linear has two roles.** It delivers operational fixed forms **and** is the **field-test
  instrument**. A Linear fixed form does not need item parameters to be *delivered* — only to set a
  statistical (TIF) target. So Linear can administer **uncalibrated** items in a field study; CAT/
  LOFT/MST cannot. **Linear bootstraps the data the others depend on.**
- **Field-test forms** are assembled by **content blueprint only** (no TIF target, because there are
  no numbers), *or* seeded with **provisional** numbers for a rough target.
- **Two calibration paths**, both first-class and provenance-flagged:
  - **Empirical** — IRT (mirt) on real field-study responses → `a, d, c` + SE/covariance. The real
    thing; what high-stakes operational use requires.
  - **Provisional** — AI-predicted / family-borrowed (`radical_config`) estimates that *seed* the
    placeholders so field-test forms can target a rough TIF and warm starts are possible. **Flagged
    `provisional` and replaced** by empirical estimates once field data lands. SE/covariance keeps
    them honest (provisional carries wide/typed uncertainty; empirical carries real mirt covariance,
    which is also what robust/chance-constrained ATA objectives need).
- **Write-back keys on the immutable item id (§6).** A *different* system writes parameters *later*
  onto the item the authoring system created — only possible if the id never changed.

---

## 6. Identity discipline — one immutable id, carried everywhere

The rename `instance_id → item_id` is trivial; the **identity contract** is load-bearing:

> **Adopt item-factory's `instance_id` as the canonical `item_id` verbatim, and never re-mint it.**
> One id, born at generation, carried unchanged through authoring → field study → calibration →
> ingestion → administration → exposure tracking → Sessions. It is the single join key.

**AMENDED by item-factory's issue-#1 reply (2026-07-09) — the identity epoch.** Today's
`instance_id` is minted as `{template_id}_{selection_index}`: unique within an export but **not
immutable across regenerations**, and a planned **purge + full-regeneration campaign** will re-mint
the entire bank. The contract therefore starts at the **post-campaign identity epoch**:
- **Pre-epoch ids (anything exported today) must never be used as calibration join keys.**
- From the epoch onward item-factory guarantees global uniqueness + immutability (regeneration
  mints a NEW id + provenance link, never reuses one), and exports a **content hash** alongside —
  a defense-in-depth check that an id still denotes the same content. Ingest SHOULD verify it.
- Field studies / calibration therefore begin only on the post-epoch bank (this composes with
  §11's Linear-first bootstrap — no schedule change, just an explicit starting line).

The danger is **re-identification**, not the name: if ingestion mints a new id, the calibration
engine can't find the item to attach numbers to, and exposure/results can't be traced back. Carry
alongside the unique id:
- **`template_id`** — the family/parent the item came from.
- **`radical_config`** key — the isomorph/"calibration grouping": clones that may calibrate together
  and that you may want to dedupe/co-constrain when banks are combined.
- **content hash** (post-epoch) — verify on ingest; a changed hash under an unchanged id is a
  contract violation to surface, never to silently accept.

---

## 7. Canonical schema sketch (superset, status-gated)

One canonical item record = the **superset** across both stages; a module ignores fields it doesn't
use. IRT fields are **nullable from birth** (an `approved`/`uncalibrated` item legitimately has
none). Indicative shape (names to finalise against the real export):

```
item_id            (str, immutable, == item-factory instance_id)   # §6
template_id        (str)            # family/parent
radical_config     (obj)           # isomorph / calibration-grouping key

# editorial axis (A)
editorial_status   (enum)          # generated|in_review|approved|rejected|in_operation|quarantined|retired|archived

# content / cognitive tags  (from item-factory; flattened to a tag dict)
tags               (dict)          # {content, cognitive(Bloom + TIMSS), kc, complicator, ...}
enemy_of           ([id])          # bare item ids (item-factory ships {enemy_id,reasons,type}; we map)
stem/options/key   (display)       # scoring is model-driven, not the literal key

# calibration axis (B)  — NULLABLE until calibrated
calibration_status (enum)          # uncalibrated|provisional|field_calibrated|operational_calibrated|recalibrating|invalidated
calibration_source (enum)          # none|ai_predicted|field_study:<id>
calibration_sample (id, nullable)  # linking group / study (see §8)
metric             ({scaling_d, form, kind})   # required ONCE parameters exist (CLAUDE.md rule 4)
a, d, c, u         (float, nullable)
se_a, se_d, cov_ad, se_b   (float, nullable)   # empirical pools; never fabricated for provisional/synthetic
```

This extends, rather than replaces, today's `ItemParameters` / `PoolItem` (`tags`, `enemy_of`,
nullable SEs, `kind` already exist).

---

## 8. Implications for machinery we already built

- **Form-governance psychometric gate gains teeth.** L2a `psychometric_review` can enforce: *are the
  constituent items field-calibrated?* A form built on provisional/uncalibrated items is blocked or
  flagged there.
- **Form-QA report must be calibration-aware.** SE(θ), TIF, reliability are meaningful only with real
  numbers; on a field-test form of uncalibrated items they are undefined — QA must say so, not
  compute nonsense.
- **Exposure tracking spans the loop.** Field-test administration *is* exposure; the L2c longitudinal
  layer must count/distinguish **field-test vs operational** exposure.
- **Comparability vs linking (forward flag).** `field_calibrated` always means "on the θ scale of a
  particular sample." Combining multiple field studies/banks is **linking/equating** — distinct from
  the design-time **comparability** report (L2b), which assumes a common scale rather than deriving
  it. Axis B carries the calibration sample / linking group so this is representable; solving it is
  downstream of v1.

---

## 9. Parked finding folded in — `g` vs `c` (lower asymptote)

At Stage B, item-factory/cat-platform name the 3PL lower asymptote **`g`** (mirt-native);
tests-platform names it **`c`**. **Same parameter** (lower asymptote of the ICC) — interchangeable
*value*, no scaling. Treat `g` as an **ingest alias** of canonical `c`, with two assertions at
ingest: value ∈ [0,1]; `u` defaults to 1.0 when absent (3PL→4PL generalisation). The label `c`
("pseudo-chance") is preferred over `g` ("guessing") per Lord's caution. Not a Stage-A concern (no
parameters there).

---

## 10. Open questions / ownership (updated after the issue-#1 reply, 2026-07-09)

1. **Who runs the calibration stage** (field responses → mirt → write-back)? **DECIDED
   (2026-07-09): tests-platform owns the calibration engine.** Rationale: responses are born
   here (the Linear field-study loop is ours end-to-end); the mirt machinery already runs here
   (`engines/scoring-r`); and the write-back boundary is neutralized because item-factory owns
   a defined **parameter write-back schema** in its bank regardless. The engine seeds as an
   **Analysis module on `scoring-r`** (single response-based-IRT source of truth; first brick =
   the `p2-analysis-module-seed` PR from the item-calibration repo), with a standalone service
   as a later refactor only if scale demands it.
2. **Where do parameters get joined onto item ids** — **ANSWERED in part:** item-factory will define
   the write-back schema in its bank; the engine (wherever it lives) writes to that defined place.
3. **Which artifact do we ingest** — **ANSWERED: the SQLite-derived CAT-ready export.** It is
   cumulative across runs, carries the item **status lifecycle** (administrability), and is where
   calibration parameters write back; `item_bank.json` is demoted to a per-run diagnostic snapshot
   (non-contractual). The split-brain fix (R1a: columns + Phase-6 threading) lands with the
   regeneration campaign, so the schema arrives on an empty bank — born complete, no backfill.
4. **Provisional-parameter policy** — do/which programs permit field-test rough targets or CAT warm
   starts on `ai_predicted` numbers?
5. **Data-layer reality** — "common dataset" as one shared DB, or one canonical schema + an
   export/ingest contract across the two repos/instances? (Near term: the latter.)

---

## 11. What this changes about build order

CAT/LOFT/MST are **gated on calibrated items**; calibration needs administration; only **Linear** can
administer uncalibrated items. So **Linear-first is forced, not merely convenient** — it is the
bootstrap that produces the field data the other modules require. This strengthens (does not change)
the existing v1 = Linear, fast-follow = CAT/LOFT/MST sequencing.

> Investigation/design only. Pin the item-factory export seam and decide §10 ownership before any of
> §5–§8 is built. Links: [[one-platform-common-bank]].
