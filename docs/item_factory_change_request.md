# Change Request — item-factory-source export, for the shared item bank

**To:** owner(s) of `outsmart-college/item-factory-source`
**From:** tests-platform (Tests module — Linear/CAT/LOFT/MST over a shared item bank)
**Date:** 2026-06-30
**Status:** request for discussion — **no work started**; grounded in the read-only investigation
(`docs/item_factory_seam_investigation.md`, item-factory HEAD `5c3a0a6`).

## Why
We're designing **one shared item bank** that feeds every administration module (see
`docs/common_item_bank_design.md`). item-factory is the **authoring source** (Stage A: content,
tags, enemies, status — no IRT parameters, which come later from field calibration). The investigation
found that item-factory **authors** everything we need, but its **export** doesn't surface it cleanly.
None of the asks below concern IRT parameters — those are out of item-factory's scope by design.

## Requests (in priority order)

### R1 — Make the CAT-ready export complete (fix the JSON/SQLite split-brain) — **high**
Today Phase 6 writes two artifacts: `item_bank.json` (carries `enemy_of`, Bloom, misconception
sources, radical/incidental config) and `item_bank.sqlite`. But the SQLite `items` table has **no
columns** for those fields, so `exporter.export_cat_ready()` writes them as **`None` placeholders**
(`src/item_bank/exporter.py` `_cat_row()`; columns absent in `src/item_bank/schema.sql`). Net: the
SQLite-derived "CAT-ready" export is hollow; only the legacy `item_bank.json` is authoritative.
**Ask:** either (a) add the content-tag/enemy columns to the SQLite items table and thread them
through Phase 6 so `export_cat_ready()` is complete, **or** (b) formally bless `item_bank.json` as the
export contract and version it. Either is fine — we need **one** complete, authoritative export.

### R2 — Promote TIMSS cognitive level onto the item — **high**
The TIMSS cognitive level (`d3a`: Knowing/Applying/Reasoning) is a primary **cognitive** dimension for
our blueprints, but it currently lives only in `rater_outputs.parsed_json` (a review artifact), not on
the item. **Ask:** surface a single agreed cognitive value as a first-class item field in the export.

### R3 — Emit a flat content/cognitive tag dict — **medium**
The blueprint consumes `tags: {dimension: value}`. Today the dimensions are scattered across
`template_id` (encodes domain/unit/KC/complicator), the `complicator` field, `bloom_process`,
`bloom_knowledge`, and the d3a above. **Ask:** emit a flattened `tags` map with agreed keys
(e.g. `domain, unit, kc, complicator, bloom_process, bloom_knowledge, timss_cognitive`) so consumers
don't parse the id or merge sources. (If you'd rather we parse `template_id`, document its grammar as a
stable contract instead.)

### R4 — Guarantee a stable, immutable item id — **high (cheap)**
We will adopt item-factory's `instance_id` as the canonical `item_id` **verbatim and never re-mint
it** — it must remain the single join key when field-calibration writes parameters back later.
**Ask:** confirm `instance_id` is globally unique and immutable across regenerations/exports, and keep
exporting `template_id` and the `radical_config` (isomorph / "calibration grouping") key alongside it.

### R5 — enemy_of shape — **low**
item-factory ships `enemy_of` as `[{enemy_id, reasons, type}]`; we need bare ids and can map it
ourselves. **Ask:** just keep `enemy_id` stable and the structure documented — no change needed unless
convenient to also provide a bare-id list.

## What we are NOT asking for
- **IRT parameters / SEs / metric.** Out of scope for item-factory — produced downstream by field
  calibration (mirt). We'll write them back onto your `item_id`.
- Any change to your review/calibration (IRR/MFRM) internals.

## Open question for you
Which artifact should we treat as the contract — `item_bank.json` or the SQLite CAT-ready export?
(R1 resolves this either way.)
