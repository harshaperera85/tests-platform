# Change Request — item-factory-source export, for the shared item bank

**To:** owner(s) of `outsmart-college/item-factory-source`
**From:** tests-platform (Tests module — Linear/CAT/LOFT/MST over a shared item bank)
**Date:** 2026-07-08 (supersedes the 2026-06-30 draft)
**Status:** request for discussion — grounded in the read-only investigation
(`docs/item_factory_seam_investigation.md`, first at HEAD `5c3a0a6`, re-verified
2026-07-07) and in working code on our side that now **consumes your exports**.

## Framing

We know item-factory is itself still in flight — so read these as **design input to
your in-flight roadmap**, not defect reports against finished software. Everything
below is far cheaper to fold into work you're already doing than to retrofit later;
that's why we're sending it now.

Context: we're building **one shared item bank** that feeds every administration
module (design: `docs/common_item_bank_design.md`). item-factory is the **authoring
source** (Stage A: content, tags, enemies, status — no IRT parameters, which come
later from field calibration). Two of your artifacts are now **load-bearing inputs**
to tests-platform:

1. the **item export** (future input to our real pool importer), and
2. the **per-unit curriculum JSON** (`domains/*/data/unit-*.json`) — already consumed
   *verbatim* by our curriculum→blueprint generator (`POST /blueprints/generate`);
   the pre-algebra course ships in our repo as its catalog.

None of the asks concern IRT parameters — those are out of item-factory's scope by
design.

## Requests (in priority order)

### R1 — Make the CAT-ready export complete (fix the JSON/SQLite split-brain) — **high**
Today Phase 6 writes two artifacts: `item_bank.json` (carries `enemy_of`, Bloom,
misconception sources, radical/incidental config) and `item_bank.sqlite`. But the
SQLite `items` table has **no columns** for those fields, so
`exporter.export_cat_ready()` writes them as **`None` placeholders**
(`src/item_bank/exporter.py` `_cat_row()`; columns absent in
`src/item_bank/schema.sql`). Net: the SQLite-derived "CAT-ready" export is hollow;
only the legacy `item_bank.json` is authoritative.
**Ask:** either (a) add the content-tag/enemy columns to the SQLite items table and
thread them through Phase 6 so `export_cat_ready()` is complete, **or** (b) formally
bless `item_bank.json` as the export contract and version it. Either is fine — we
need **one** complete, authoritative export. If completing the export is already on
your roadmap, aligning its shape with R3 below costs one conversation now.

### R2 — Flow the authoring-time cognitive tags into the export — **high**
Cognitive tagging already happens **once, at template-authoring time**
(`src/template_specs.py: TemplateSpec`) — the right place, and we build **no**
tagging machinery on our side (your tags are read-only imported attributes for us).
But the TIMSS cognitive level currently surfaces only in review artifacts
(`rater_outputs.parsed_json`), not on the exported item.
**Ask:** carry the template's cognitive values onto each exported item —
`bloom_process`, `bloom_knowledge`, and the TIMSS level (your
`timss_classification`, our dimension `timss`: Knowing | Applying | Reasoning).

### R3 — Emit a flat content/cognitive tag dict with these agreed keys — **medium**
Our blueprints consume `tags: {dimension: value}`. We've now pinned the dimension
vocabulary on our side, so this is a concrete proposal rather than an open design
question. **Ask:** emit a flattened `tags` map per item with:

| key | value |
|---|---|
| `domain` | e.g. `PA` / `CA` |
| `unit` | the unit's **id from the unit JSON, verbatim** |
| `kc` | the KC's **id from the unit JSON, verbatim** |
| `complicator` | the complicator id/index |
| `bloom_process` | Remember / Understand / Apply / Analyze / Evaluate / Create |
| `bloom_knowledge` | Factual / Conceptual / Procedural / Metacognitive |
| `timss` | Knowing / Applying / Reasoning |

The `unit`/`kc` values matching the curriculum JSON ids **verbatim** is the important
part: our generated blueprints already constrain on those exact ids, so items tagged
with the same ids assemble with **zero mapping layer** on either side. (If you'd
rather we parse `template_id`, document its grammar as a stable contract instead —
but the flat dict is strongly preferred.) Note: **no DOK key** — DOK isn't tagged in
item-factory yet; we deliberately reject `dok` constraints until it exists upstream.

### R4 — Guarantee a stable, immutable item id — **high (now a dependency, cheap)**
We have **adopted** `instance_id` as the canonical `item_id`, verbatim, never
re-minted — it is the single join key when field calibration writes parameters back.
**Ask:** confirm `instance_id` is globally unique and immutable across
regenerations/exports, and keep exporting `template_id` and the `radical_config`
(isomorph / calibration-grouping) key alongside it.

### R5 — enemy_of shape — **low**
You ship `enemy_of` as `[{enemy_id, reasons, type}]`; we need bare ids and can map it
ourselves. **Ask:** just keep `enemy_id` stable and the structure documented — no
change needed unless convenient.

### R6 — Treat the per-unit curriculum JSON as a versioned contract — **new, medium**
The unit JSON shape (`{course_id, course_name, unit_id, unit_order, unit_name,
knowledge_components: [{id, order, name, complicators: [{id, order, name, …}]}]}`,
verified consistent across all 11 pre-algebra files, 2026-07-07) is now consumed
**verbatim** by our blueprint generator, and the ids in it are the same ids R3's
`unit`/`kc` tags must carry.
**Ask:** treat that shape as a stable, versioned contract — or tell us before it
changes. (Extra keys are fine — we ignore what we don't consume, e.g. complicator
`examples`/`misconceptions`.)

## What we are NOT asking for
- **IRT parameters / SEs / metric.** Out of scope for item-factory — produced
  downstream by field calibration (mirt). We'll write them back onto your `item_id`.
- Any change to your review/calibration (IRR/MFRM) internals.
- Any **new tagging** beyond what `TemplateSpec` already authors (R2 is surfacing,
  not adding).

## Open questions for you

1. **Which artifact is the contract** — `item_bank.json` or the SQLite CAT-ready
   export? (R1 resolves this either way; we just need the answer.)
2. **Timing:** for each ask, roughly when could it land in your roadmap? A pinned
   contract with a delivery date is as useful to us as the artifact itself — we can
   build our importer against agreed fixtures and drop the real export in later.
3. **Calibration-engine ownership** (bigger than this CR, but this is the natural
   venue to start it): *someone* must own the downstream engine that takes field-study
   responses → mirt calibration → writes `a/d/c/u` + SEs back onto your `item_id`s
   (design: `docs/common_item_bank_design.md` §10). It could live in item-factory, in
   tests-platform, or standalone. We don't need a decision now — we need the
   conversation started, because both sides' roadmaps depend on the answer.
