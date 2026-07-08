# BP-MODES-1: Blueprint Delivery-Mode Semantics

**Spec ID:** BP-MODES-1 (supersedes draft BP-CAT-1)
**Status:** Draft for review
**Date:** 2026-07-07
**Applies to:** `tests-platform` `app/schemas/blueprint.py` (Blueprint) and every
engine consuming blueprints for delivery: fixed-form assembly, LOFT, CAT
**Destination:** `tests-platform/docs/` (authored in the Ignite CAT repo during
design review; move on adoption)
**Author:** drafted by Claude for Harsha Perera

---

## 0. Purpose and scope

The tests-platform `Blueprint` is a delivery-mode-agnostic assembly
specification, currently consumed only by batch fixed-form assembly (`mip`,
`random_constrained`). This spec defines what every blueprint field means under
each of the three delivery modes — **fixed form**, **LOFT** (linear-on-the-fly),
and **CAT** — so that one blueprint object is satisfiable by all three, and
"satisfies the blueprint" has a precise, testable meaning per mode.

Schema changes are minimal (two relaxations, one reservation); most of this
spec is consumer semantics. Nothing here changes existing fixed-form behavior.

Keywords MUST / MUST NOT / SHOULD / MAY are used in the RFC-2119 sense.

## 1. The mode model

The three delivery modes differ on exactly two axes:

- **Assembly moment** — when items are chosen: ahead of time (batch), at
  session start, or during the session per item.
- **Length fixity** — whether the number of items is known before delivery.

Every field's per-mode meaning follows from those two axes:

| Field | Fixed form <br>*(batch · fixed length)* | LOFT <br>*(per session · fixed length)* | CAT <br>*(per item · emergent length)* |
|---|---|---|---|
| `length` | binding: items per form | binding: items per session form | **not binding** — CAT config's `min_items`/`max_items` govern (§3.2) |
| `num_forms` | forms in the batch job | **not binding** — one form per session, unbounded | not binding |
| count/proportion bounds | exact, resolved at compile | exact, resolved at compile — **identical to fixed form** | running/final semantics (§3) |
| `statistical_target` (TIF) | the assembly objective | **RECOMMENDED** — the parallelism guarantee (§4.1) | **ignored** — the stopping rule owns precision (§2.1) |
| `enemy_policy` | per form | per form, unchanged | selection-time masking (§3.3) |
| `exposure_target.max_use_per_item` | binding across the batch | N/A — no finite batch (§4.2) | N/A (§2.3) |
| `exposure_target.max_pairwise_overlap` | binding across the batch | N/A — not enforceable online (§4.2) | N/A |
| `exposure_target.max_exposure_rate` | → use cap via `num_forms` | **running cap against the exposure ledger** (§4.2) | N/A — administration-time control (S-H) owns it |
| `exposure_feedback` (longitudinal) | eligibility masking | eligibility masking, unchanged | eligibility masking, unchanged |
| `segments` | reserved (§2.4) | reserved | reserved |

Consumers MUST implement the column for their mode and MUST NOT borrow
another column's interpretation.

## 2. Schema amendments

### 2.1 A1 — `statistical_target` becomes optional

```python
class Blueprint(BaseModel):
    ...
    statistical_target: TIFTarget | None = None   # was: TIFTarget (required)
```

A blueprint with `statistical_target = None` is a **content-only blueprint**.

Per-mode rules:

1. **Fixed form:** strategies consuming a content-only blueprint MUST assemble
   for feasibility only (no TIF objective) and MUST still report realized TIF.
2. **LOFT:** `statistical_target` is RECOMMENDED (§4.1). Content-only LOFT is
   legal (low-stakes quizzes) but forms are then parallel in content only —
   consumers SHOULD surface this as an authoring-time notice.
3. **CAT:** consumers MUST ignore `statistical_target` and SHOULD emit a
   validation warning if present ("TIF target present on a blueprint bound to
   CAT delivery; it will not be enforced"). A static TIF curve is a fixed-form
   concept: CAT's information target moves with the theta estimate, and its
   statistical requirement is the stopping rule (SE ≤ 0.3 ⇔ TIF ≥ ~11.1 at the
   final theta).

Backward compatible: all stored v1 blueprints carry the field and remain valid.

### 2.2 A2 — CAT conformance semantics

Defined in §3 (normative).

### 2.3 A3 — exposure semantics are per-mode

`exposure_target.max_use_per_item` and `.max_pairwise_overlap` are batch
concepts and apply to fixed-form assembly ONLY. Adaptive and LOFT engines MUST
NOT attempt to enforce them (LOFT reinterprets only `max_exposure_rate` — §4.2;
CAT leaves all administration-time exposure to its own config, e.g.
Sympson-Hetter). Consumers SHOULD warn when a blueprint carrying batch-only
exposure fields is bound to a mode that ignores them.

`exposure_feedback` (longitudinal, opt-in) applies to **all three modes** as
eligibility masking.

Note for authors: `max_exposure_rate` and Sympson-Hetter's rmax are the same
quantity in different frames (share of administrations containing the item).
They are deliberately not unified: one governs assembly jobs, the other a
stochastic administration policy. Setting one does not set the other.

### 2.4 A4 — reserved: `segments`

Composite tests (Smarter Balanced pattern: an adaptive segment plus a fixed
performance-task segment under one blueprint) are out of scope for GTM but
anticipated:

```python
class Blueprint(BaseModel):
    ...
    segments: list["BlueprintSegment"] | None = None   # reserved; None for now
```

Non-normative sketch: when `segments` is present, top-level `length` /
`content_constraints` / `statistical_target` are disallowed and each segment
carries its own plus a `delivery_mode`. Validators SHOULD reject `segments`
until the extension is specified — the name is burned, the behavior is not.

## 3. CAT conformance semantics (normative)

What it means for an adaptively administered session to satisfy a
`ContentConstraint` list, and what the delivering engine MUST guarantee.

### 3.1 Definitions

- **Session item set** `S`: items administered in one completed CAT session.
- **Realized length** `L = |S|`: emergent, bounded by the CAT config's
  `min_items` / `max_items`.
- **Member set** `M(c)`: pool items matching all tag predicates of constraint
  `c` (identical to the fixed-form compiler's `ContentSet.members`).

### 3.2 Bound interpretation under variable length

- `length`: not binding (see §1). Generators SHOULD set it to the intended
  `max_items` for documentation value.
- `mode="count"`, `minimum` m: at completion, `|S ∩ M(c)| ≥ m` — a
  **final-form requirement** that gates stopping (§3.4).
- `mode="count"`, `maximum` M: `|S ∩ M(c)| ≤ M` at all times — enforced by
  eligibility masking (§3.3); never violable.
- `mode="proportion"`: interpreted against realized length. Engines MUST use
  proportion bounds as running targets during selection and satisfy them at
  completion within integer-rounding slack: a proportion minimum is satisfied
  iff `|S ∩ M(c)| ≥ floor(min_p · L)`; a maximum iff `|S ∩ M(c)| ≤ ceil(max_p · L)`.
  This is deliberately one-sided-lenient; programs needing exact cells MUST
  express them as counts.

### 3.3 Enforcement architecture

Per administered item, the CAT engine MUST:

1. **Mask hard-ineligible items** — items whose administration would
   irrecoverably violate the blueprint: members of any constraint already at
   its maximum (counts resolved at `max_items`), enemies of administered items,
   and items hard-excluded by `exposure_feedback.max_cumulative`.
2. **Check forward feasibility** — after masking, a completion of the session
   within `max_items` satisfying all minimums MUST still exist. If
   administering candidate `i` would make some minimum unsatisfiable
   (remaining capacity < remaining required items), `i` MUST be masked for
   this step.
3. **Prioritize among eligible items** — SHOULD use a priority-index method
   (weighted-deviations or maximum-priority-index): reference formulation
   `priority(i) = info(i, θ̂) · Π_{c : i ∈ M(c)} f(c)` where `f(c) ≥ 1` grows
   with (remaining minimum for c) / (remaining capacity). Pure
   max-information is recovered when all minimums are met.
4. **Record constraint state** (running counts per constraint) in the session
   audit log at every step, so conformance is verifiable post hoc.

Implementation note (Ignite): steps 1–2 compute an eligible-item subset in the
orchestrator; the existing mirtcat-service `rank_items(criteria, subset)`
endpoint ranks within it; step 3's weighting applies orchestrator-side to the
ranked list. No R-side changes are required for a first implementation.

### 3.4 Stopping-rule interaction (the gate)

1. A session MUST NOT stop — even with the SE criterion met — while any
   minimum is unsatisfied **and** satisfiable within `max_items`.
2. On reaching `max_items` the session ends regardless. If any minimum is then
   unsatisfied (pool exhaustion, masking conflicts), the session MUST complete
   and MUST be flagged `blueprint_conformant = false` with the violated
   constraints listed. Engines MUST NOT abort a live examinee session for
   blueprint reasons.
3. The CAT config's `min_items` and the blueprint gate compose; both must
   clear before stopping.
4. Authoring-time validation MUST reject configurations where
   `Σ resolved count-minimums > max_items` (structurally impossible) — an
   error at save time, not a discovery at run time.

### 3.5 Conformance record

Every completed adaptive session MUST persist:

```json
{
  "blueprint_id": "…",
  "blueprint_conformant": true,
  "realized_length": 32,
  "constraints": [
    {"key": "unit=unit-3", "required_min": 5, "required_max": 8, "realized": 6, "satisfied": true},
    {"key": "KC=kc-3.2 & DOK=2", "required_min": 1, "required_max": null, "realized": 2, "satisfied": true}
  ]
}
```

## 4. LOFT conformance semantics (normative)

LOFT assembles a unique form per examinee at session start. Because length is
fixed and assembly is whole-form, **conformance is identical to fixed form**:
a candidate form either satisfies every content constraint (bounds resolved
against `length`, exactly as `blueprint_compiler` does today) and the enemy
policy, or it MUST NOT be administered. None of §3's variable-length machinery
applies.

### 4.1 Statistical parallelism

When `statistical_target` is present, a LOFT engine MUST treat the TIF
`tolerance` band as a **hard acceptance criterion**: a generated form is
administrable iff `|TIF(θ_k) − target_k| ≤ tolerance` at every theta point.
This is what makes per-examinee forms *statistically* parallel rather than
merely content-matched — the score-comparability guarantee when every examinee
sees a different form. A `statistical_target` without `tolerance` on a
LOFT-bound blueprint SHOULD be rejected at binding time (an objective with no
acceptance band is meaningless when there is no batch objective to optimize).

### 4.2 Exposure

- `max_use_per_item` / `max_pairwise_overlap`: N/A (no finite batch; pairwise
  comparison against all prior sessions is not enforceable online). Engines
  MUST ignore them; validators SHOULD warn.
- `max_exposure_rate`: reinterpreted as a **running cap** consulted against
  the longitudinal exposure ledger at each assembly: mask item `i` when
  `uses(i) / sessions ≥ rate` (both counted in the ledger's configured
  contexts). Combined with seeded randomization this is the standard and
  sufficient LOFT security lever.
- `exposure_feedback`: applies unchanged (eligibility masking + underuse bias).

### 4.3 Engine

A conforming LOFT engine MAY be implemented as either:

- **(a) randomized feasibility search** — `random_constrained` extended with
  the §4.1 acceptance test in its existing attempt loop (seeded per session);
- **(b) per-session CP-SAT solve** — tolerance band as hard constraints,
  randomized tie-breaking/objective perturbation for form diversity; or
- **(c) pre-generated form pool** — a batch fixed-form job (existing `mip`
  path, overlap-capped) whose forms are drawn per session; the most auditable
  variant, RECOMMENDED where forms must be human-reviewed before any
  administration.

All three MUST sit behind the same interface ("return a conforming form for
this session or fail loudly") and MUST persist the §4.4 record. A solver/search
failure at session start MUST fail the session start — never administer a
non-conforming form.

### 4.4 Conformance record

Same shape as §3.5 plus statistical fields; `blueprint_conformant` MUST be
true by construction (non-conforming forms are never administered):

```json
{
  "blueprint_id": "…",
  "blueprint_conformant": true,
  "realized_length": 40,
  "constraints": [ …as §3.5… ],
  "tif_actual": [4.9, 11.2, 5.1],
  "tif_target": [5.0, 11.0, 5.0],
  "tolerance": 0.5,
  "engine": "random_constrained+band",
  "seed": 91834
}
```

## 5. Consumption contract (Ignite / CAT module)

Ignite stores no blueprint entities; its `TestConfig` gains one optional block:

```python
class BlueprintBinding(BaseModel):
    blueprint_id: str | None = None      # provenance (tests-platform id)
    blueprint: dict | None = None        # embedded Blueprint JSON, verbatim
    on_nonconformant: Literal["flag", "invalidate_score"] = "flag"
```

- Blueprint JSON is **embedded at config-creation time** (fetched from
  tests-platform `/api/v1/blueprints/{id}` or pasted). Embedding — not
  referencing — keeps Ignite runnable without a live tests-platform and makes
  configs self-describing for replay and simulation.
- `on_nonconformant` sets scoring policy for sessions flagged under §3.4(2).
- Item tags: Ignite items expose `tags: dict[str, str]` assembled from
  first-class columns (`content_category` → hierarchical path per the content
  registry; `cognitive_framework`/`cognitive_level`), matching the pool-item
  tag contract fixed-form assembly already uses.

## 6. Generator note (informative; rev. 2026-07-09)

The curriculum→blueprint generator (lives in tests-platform; consumes
item-factory curriculum data: Course → Unit → KC → Complicator →
**Dimension**) emits blueprints valid under this spec.

### 6.1 Weight function (supersedes the earlier "KCs + complicators" rule)

The atomic content unit is the **dimension** (skill) inside a complicator —
item-factory selects one parent item per dimension, so pool mass is
proportional to dimension counts by construction. Weights are pure sums up
the hierarchy:

```
w(complicator) = n_dimensions        # from its kc_config; ≥ 1 by construction
w(KC)          = Σ w(complicators)   # deeper KCs weigh more automatically
w(unit)        = Σ w(KCs)            # broader/deeper units weigh more automatically
```

A single-dimension complicator weighs exactly 1; the old
count-the-complicators rule is the degenerate case where every complicator
is single-dimension. **Imputation:** where a complicator's kc_config does
not yet exist, impute the domain median dimension count and report the
imputed fraction in the generator output — blueprints built on partly
imputed weights are honestly labeled, never silently exact.

### 6.2 Test-type shapes (one generator, one weight function, four scopes)

The generator takes a `scope` parameter (unit-id subset); constraint grain
is chosen so guarantees remain arithmetically possible at each length:

| Test | Mode | Scope | Content constraints | Cognitive constraints |
|---|---|---|---|---|
| Unit quiz | LOFT | one unit | per-KC shares ∝ w(KC); plus per-complicator **maximum** (1–2) so a fixed form cannot drill one complicator | test-level marginal profile only |
| Mid-course | CAT | first-half units | per-unit shares ∝ w(unit), renormalized within scope | marginal profile (+ per-unit floors where claims require) |
| End-of-course | CAT | second-half units | same | same |
| Cumulative final | CAT | all units | per-unit shares ∝ w(unit) (thin minimums — the §7-verified regime) | marginal profile + a handful of claim-critical cells (e.g. ≥1 Reasoning per unit) |

Largest-remainder rounding throughout. Per binding mode: content-only for
CAT; TIF template + tolerance attached for fixed-form and LOFT bindings.
Generated blueprints MUST pass structural feasibility validation against
the target pool's `tag_summary` before being offered for delivery.

### 6.3 Cognitive-level claims are program-level claims

A single short test cannot support mastery claims for every
(content × cognitive) cell — the arithmetic forbids it. The program can:
quizzes sample KC × cognitive densely within units, interims sample
unit × cognitive coarsely, and course-level aggregation pools the evidence
per cell. Each blueprint therefore guarantees only what its length honestly
carries; cell-level mastery claims are certified by aggregation across the
assessment program, not by any single form.

## 7. Verification protocol (acceptance criteria)

"One blueprint satisfies all three modes" is demonstrated, not argued —
Ignite's simulation framework is the harness:

1. **Fixed form:** existing assembler compliance report; all constraints
   satisfied; TIF within tolerance when targeted.
2. **LOFT:** N ≥ 1,000 simulated sessions; 100% of administered forms
   conformant by construction; distribution of `tif_actual` within the band at
   every theta point; per-item empirical exposure ≤ `max_exposure_rate` + ε.
3. **CAT:** N ≥ 1,000 simulees per condition on a blueprint-bound config;
   100% `blueprint_conformant = true` given a feasibility-validated
   (blueprint, pool) pair; paired conditions (constrained vs. unconstrained
   MI, same seeds) report RMSE-over-N with CI bands and pairwise tests — the
   measured precision cost of the blueprint.
4. **Stress (CAT):** repeat (3) with a deliberately tight pool to exercise the
   §3.4(2) flag path; flagged sessions must carry complete conformance records.

## 8. Migration & versioning

- Add `schema_version: int = 2` to `Blueprint` (v1 = pre-amendment). Consumers
  MUST accept v1 documents (every v1 document is a valid v2 document).
- No stored-data migration; §2.1 is a relaxation, §2.3/§3/§4 are consumer
  semantics, §2.4 is inert.
- Convergence bookkeeping: this spec is the first entry of the shared contract
  set between tests-platform and Ignite (`docs/ignite-contracts/` pattern).
