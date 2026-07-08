# One Blueprint, Three Enforcement Regimes — an Explainer

**Companion to:** `docs/blueprint-delivery-mode-semantics.md` (BP-MODES-1, normative).
This document is **informative**: it explains, with a worked example from the shipped
pre-algebra curriculum, how the same blueprint is satisfied under Linear fixed-form,
LOFT, and CAT delivery, and how CAT reconciles its stopping rule and item-selection
algorithm with blueprint conformance on content and cognitive complexity.

---

## 1. A worked cell, end to end

The §6 generator derives an end-of-course (EOC) blueprint from the pre-algebra
curriculum (`app/data/curriculum/pre_algebra/`: 11 units, 60 KCs, 199 complicators).
Per the §6 recipe, each unit's weight is **its KCs + its complicators**, and the
course total is the sum over units:

- **Unit 3 — Fractions and decimals:** 8 KCs + 32 complicators = weight **40**
- **Course total:** 60 KCs + 199 complicators = **259**

So Unit 3's raw share is 40/259 ≈ 0.1544. At a requested length of 60, its quota is
9.266 items, which **largest-remainder rounding** resolves to **9 items** (counts
across all 11 units sum to exactly 60 by construction: 6/5/9/4/6/6/6/4/6/5/3).

How that allocation is *encoded* depends on the delivery binding:

- **fixed_form / loft** → a **count** cell: `unit=<unit-3-id>, min = max = 9`.
- **cat** → a **proportion** cell: `min = max = 9/60 = 0.15`.

Note the emitted proportion is the **rounded share** (9/60 = 0.15), not the raw
40/259: rounding once, at generation, keeps the full set of proportions
self-consistent — they resolve back to counts that sum exactly to the length, with
no independent-rounding drift.

## 2. The mode model — why the encodings differ

The three modes differ on exactly two axes (spec §1): **when items are chosen** and
**whether the length is known in advance**.

| | Linear fixed | LOFT | CAT |
|---|---|---|---|
| Items chosen | ahead of time, whole batch | at session start, whole form | **during the session, one at a time** |
| Length | fixed | fixed | **emergent** — stopping rule decides, bounded by `min_items`/`max_items` |
| Cell encoding (generated) | count 9 = 9 | count 9 = 9 | proportion 0.15 |
| "Satisfies the blueprint" means | solver output has exactly 9, checked **before anything exists** | each generated form has exactly 9 **or it is never administered** | at completion, `floor(0.15·L) ≤ x ≤ ceil(0.15·L)` for the **realized** length L (§3.2) |
| Statistical guarantee | TIF objective (minimax/maximin) optimized at assembly | TIF tolerance band = **hard acceptance criterion** (§4.1) | the **stopping rule** owns precision; a static TIF target is ignored (§2.1) |
| Enforcer | OR-Tools CP-SAT, this repo | per-session solve/search behind the §4.3 interface (later phase, this repo) | the Ignite CAT engine's selection loop + stopping gate (§3 — Ignite-owned) |

**Why counts are wrong for CAT.** A count cell says "exactly 9 items," full stop.
But a CAT session may legitimately stop at 34 items (SE criterion met early): 9 of 34
is a very different content mix than 9 of 60 — and the *sum* of count minimums (60)
would exceed a typical `max_items` (say 40), making the blueprint structurally
unsatisfiable; §3.4(4) requires rejecting exactly that pairing at authoring time. A
**proportion** cell says "15% of whatever test this examinee ends up taking": at
L = 60 it resolves to 9; at L = 34 to the floor/ceil band 5–6. Same intent,
scale-free. Hence the generator's binding-aware emission (`constraint_mode`
overrides it in either direction when a program needs to).

## 3. How CAT honors a blueprint while staying adaptive

A CAT has three "wants" pulling on every item choice: the **selection algorithm**
wants maximum information at the current θ̂; the **stopping rule** wants to end as
soon as SE is small enough; the **blueprint** wants the final content/cognitive mix
honored. The spec resolves this by giving each a distinct, non-overlapping job:

1. **The stopping rule owns statistical precision** — which is why the TIF target is
   *ignored* for CAT (§2.1). A static TIF curve is a fixed-form concept: CAT's
   information target moves with θ̂, and "SE ≤ 0.3" *is* its statistical requirement
   (≈ TIF ≥ 11 at the final theta). CAT-bound generated blueprints are therefore
   content-only.
2. **The blueprint constrains item selection, per item** (§3.3). Before ranking by
   information the engine must: **mask** hard-ineligible items (members of any cell
   already at its maximum — for proportion cells, resolved at `max_items` —, enemies
   of administered items, over-exposed items); **check forward feasibility** (never
   administer an item that makes some minimum unsatisfiable within the remaining
   capacity); and **prioritize** the survivors,
   `priority(i) = info(i, θ̂) · Π f(c)`, where `f(c) ≥ 1` grows as cell `c` falls
   behind its minimum relative to remaining capacity. Once all minimums are met this
   **degrades gracefully to pure maximum-information CAT** — the blueprint bends
   selection only when it must.
3. **The blueprint gates stopping** (§3.4) — the single point where the two systems
   meet. A session may **not** stop, even with the SE criterion satisfied, while any
   minimum is unmet-but-still-satisfiable. Conversely, at `max_items` the session
   ends regardless — a live examinee is never held hostage to the blueprint — and
   unmet minimums produce `blueprint_conformant: false` with the violated cells
   listed (§3.5); scoring policy (`flag` vs `invalidate_score`, §5) takes it from
   there.

**Cognitive complexity rides the identical machinery.** The generator's authored
cognitive profile (pinned dimensions `bloom_process` / `bloom_knowledge` / `timss`;
tags are read-only item-factory attributes) emits distribution cells as proportions —
already scale-free — and per-unit minimums as cross-classified `{unit × dimension}`
cells that become masks and priority terms exactly like content cells. One deliberate
nuance: per-unit **minimums stay absolute counts even under CAT** — "at least 2
Reasoning items in Unit 3" is a floor irrespective of length — which is why
§3.4(4)'s authoring-time check (Σ resolved minimums ≤ `max_items`) exists at the
binding step.

**Division of labor across the platform:** tests-platform *authors and validates*
blueprints (the §6 generator, the feasibility gate against a pool, and the binding-
time checks); the **Ignite CAT engine implements §3** — masking, forward
feasibility, priority index, the stopping gate, and the per-session conformance
record. §3 is out of scope for this repo permanently-for-now; it arrives with the
CAT-module merge.

## 4. LOFT, for contrast

LOFT needs none of §3's variable-length machinery. Length is fixed and assembly is
whole-form, so conformance is **identical to fixed form** (§4): a candidate form
either satisfies every count cell and the enemy policy or it is never administered,
and when a TIF target is present its tolerance band is a **hard acceptance
criterion** — the score-comparability guarantee when every examinee sees a different
form. LOFT is much closer to Linear than to CAT; it is a later phase in this repo.

## 5. Shadow-test CAT (a.k.a. "shadow CAT") — the upgrade path

The §3.3 masking + priority-index approach is a *heuristic*: it can paint itself
into corners near the end of a session (pool exhaustion, conflicting cells), which
is what the §3.4(2) non-conformance flag is for. The stronger method is the
**shadow-test approach** (van der Linden & Reese): before administering each item,
solve a **complete fixed-form ATA model** — the "shadow test" — of the full
remaining length, satisfying *every* blueprint constraint and maximizing information
at the current θ̂; administer the single best not-yet-seen item *from* that shadow
test; update θ̂; re-solve.

- **It is still, fully, a CAT**: every selection depends on the running θ̂; the
  examinee's path adapts item by item. The shadow forms are throwaway planning
  artifacts the examinee never sees.
- Its advantage: blueprint conformance is **guaranteed by construction** — the final
  shadow test *is* the administered test — rather than pursued greedily.
- Its cost: a MIP solve per administered item. Notably, the solver it needs is
  exactly the fixed-form CP-SAT model this repo already owns, which is why
  shadow-test ATA is reserved (CLAUDE.md golden rule 6) as a natural later upgrade
  to the CAT module rather than an architectural change — the assembly engine would
  simply gain a per-step caller.

---

*Generated blueprints against today's simulated pools flag as infeasible on the
unit/KC cells — the demo items don't carry the real curriculum's identifiers. That
resolves when the real pool importer lands: both sides key on the same verbatim
`unit_id` / KC `id` from the item-factory export.*
