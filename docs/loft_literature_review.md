# LOFT engine vs. the literature — determination & improvement proposal

**Date:** 2026-07-10. **Scope:** the §4 LOFT engine (`engine/strategies/loft.py` +
`assembly/loft.py`, commit `c45e9a3`) evaluated against four sources read in full:

1. **Han (2026)** — *AllTestSim (ATS)* user's manual + hantest.net/alltestsim/
   (APM, doi:10.1177/01466216261449756). Unified simulation tool: Fixed | LOFT |
   MST-R | MST-S | SCAT | CAT.
2. **Embretson, Thierbach & Walsh (2025)** — *LOFT: Which Design to Choose?* (IMPS
   proceedings; USAF-sponsored Monte Carlo of LOFT designs vs parallel linear forms).
3. **Luecht & Sireci (2011)** — *A Review of Models for CBT* (College Board RR
   2011-12; the canonical eight-model delivery taxonomy).
4. **Choi & Lim** — *TestDesign 1.7.0* CRAN manual (the GPL MIP package this repo
   already uses as its validation oracle).

---

## 1. Determination: where the engine stands

**On assembly rigor the engine meets or exceeds every standard in these sources.**

- **Conformance semantics validated.** Luecht & Sireci class LOFT as "a variation of
  preassembled test forms" with whole-form conformance to "a single target test
  information function … and a constant set of test specifications" — exactly the
  §4 reading we implemented. Forms being unique-but-overlapping is expected
  ("there is typically some overlap of items allowed across the test forms").
- **The engine subsumes the empirically-recommended designs.** Embretson et al.'s
  winners (Dipping Bins / Balanced Bins — difficulty-balanced stratified sampling)
  achieve RMSE parity with linear forms; their losers (Random Forms, Unbalanced
  Bins) fail through uncontrolled difficulty and degraded tails. Our TIF tolerance
  band at every θ point *strictly dominates* bin-based difficulty control, and the
  content cells + enemy exclusion go beyond anything they simulate. Their paper
  contains no optimization-based variant at all; our CP-SAT engine exceeds the
  frontier they tested.
- **The exposure levers match the named mechanisms.** Assembly-time eligibility
  filtering of at-risk items + rate caps + random sampling are precisely Luecht &
  Sireci's LOFT security levers; ATS's LOFT (greedy TIF *shaping*, 7 fixed θ
  points, no acceptance band) is *weaker* than our band-acceptance design — as a
  simulation tool it shapes toward targets, it does not certify conformance.
- **Fail-loudly + conformance records match operational doctrine** ("system
  generated test form identifiers for every LOFT form"; automated per-form QC when
  human review is impossible).

**Verdict: the engine is not below the literature's standards on assembly — the
substantive gaps are in *evaluation evidence*, *exposure-control maturity*, and one
un-built engine variant.** Detailed below, converging across sources.

## 2. Gaps and improvement proposal (prioritized)

### G1 — Measurement-simulation harness (the big one; convergent across all four)

> **STATUS: BUILT (2026-07-11).** `POST /simulations` — `app/simulation/harness.py`
> + `app/schemas/simulation.py` + `app/api/v1/simulation.py`; same-engine doctrine
> (only the examinee is simulated), item-level-paired comparisons, §4-format
> report. See `docs/backlog.md` Done entry. The ATS-exporter oracle below remains
> open (optional follow-up).

We have no population-level θ-recovery simulation for linear or LOFT. Embretson's
*entire* evidentiary standard is replication-based recovery parity with a linear
baseline; ATS's entire output surface is recovery + conditional diagnostics;
TestDesign ships `RMSE(conditional=TRUE)` + subgroup `RE` as first-class.

**Build:** a simulation service (shared by linear/LOFT; CAT arrives with the merge)
that runs N simulees ~ p(θ) × R replications through a design and reports:
- overall: bias, MAE, RMSE, r(θ, θ̂), reliability (r²), mean SE, θ̂ SD;
- **conditional on true θ** (bins ~0.5 wide, −3…3): CBIAS/CMAE/CSEE/CRMSE;
- **tail recovery** (|θ| > 2 scatter/regression — Embretson's Random-Forms
  diagnostic) and the **EAP-shrinkage caution**: never read low posterior SD as
  precision; report θ̂ SD and r alongside;
- **baseline comparison:** same pool, fixed linear form(s) vs LOFT sessions —
  recovery parity is the acceptance standard;
- exposure/overlap distributions tied to the run (see G3);
- infeasibility frequency + solve-time distribution (TestDesign's
  `freq_infeasible`/`solve_time` pattern).

**Conventions (adopted 2026-07-10, shared with Ignite):** the harness follows
`docs/ignite-contracts/ignite-2026-07-10-fe51314/simulation-lane-conventions.md` —
verification reports use the §4 shared format (header block with
lanes/coverage/seeds, `criterion | target | result` acceptance table,
reproduction block); **C1** (if a fast path is ever added, ONE boundary
predicate decides what may run on it — consulted by validator, worker, and
result stamping alike) and **C3** (fast paths are optimizations of the same
code path, never a second implementation of assembly/scoring semantics) apply
to our lanes from day one. Our single in-process lane makes C1 trivially
satisfied today; the conventions bind the moment that changes.

**ATS as an external simulation oracle (recommended):** ATS consumes trivial TSV
(items: `id, a1, b1, c`; examinees: `id, theta`; a 10-line syntax file), supports
`IC> LOG` (our canonical D=1), runs deterministic seeded console simulations, and
outputs the full recovery/conditional/exposure battery. An exporter
(pool → `ATSitm_`, design → `ATSsyn_`) gives us an independent cross-check of our
harness — the same pattern as eatATA for assembly. (Free, noncommercial; console
runs on macOS/Windows — not Linux, so it's a laptop-side check, not CI.)

### G2 — Engine (c): batch pre-generated form pool (spec'd, never built)

> **STATUS: BUILT (2026-07-11).** `assemble_loft_session(engine="pregenerated",
> form_pool=…)` — draw-time full conformance re-check (never administer a stale
> form), §4.2 rate cap masks whole forms, least-drawn rotation with seeded
> order-independent tie-break. Wired end-to-end: `POST /loft/sessions`
> (`test_id` → the test's PUBLISHED forms = the pool, i.e. review/approve/publish
> before anything is drawable), `LoftConfig`/`LoftStrategy` (context
> `form_pool`/`draw_counts`), the G1 harness (`LoftDesign.engine="pregenerated"`
> + `n_pool_forms` — the batch is assembled ONCE by the real `assemble()`), and
> the editor's LOFT-preview engine select. See `docs/backlog.md` Done entry.

BP-MODES-1 §4.3(c) lists it and marks it "RECOMMENDED where forms must be
human-reviewed"; Luecht & Sireci *prefer* this variant ("the primary advantage of
developing the test forms in advance is that content and measurement experts can
review each form") and note real-time LOFT's Table-1 limitation: "QA or review of
operational test forms is impossible."

**Build:** almost free — it composes existing pieces: batch `mip` multi-form
assembly (with `max_pairwise_overlap` + band tolerance) → forms enter the existing
**governance lifecycle** (review/approve/publish!) → LOFT sessions draw randomly
from the published pool. TestDesign's `Split` (minimize inter-partition TIF
difference) is the reference formulation for the batch step.

### G3 — Exposure-control maturity (TestDesign + Luecht & Sireci)

1. **Sawtooth risk:** our hard running cap admits an item until it hits the rate,
   then starves it. TestDesign's answer is probabilistic eligibility with a fading
   factor (0.999) so realized rates *converge*. First step: measure (add sawtooth
   diagnostics to the G1 harness); adopt probabilistic eligibility if observed.
2. **θ-segment-conditional exposure reporting:** LOFT can't condition assembly on
   θ (no estimate pre-session), but the *evaluation* must report realized exposure
   by examinee θ segment — marginal caps can hide segment-hot items.
3. **Live pairwise overlap rate** (distinct metric from per-item exposure;
   TestDesign caps it at 0.20 by default) and **per-person cumulative usage**
   across administrations (retake protection) — both currently unmeasured.
4. **Shortfall diagnostics:** Luecht & Sireci fn. 3 — exposure masking interacts
   subtly with supply/constraints/targets; when the mask shrinks the pool, report
   the impact on band feasibility, not just the mask count.

### G4 — TCC (expected-score) targeting option

TestDesign targets TCC as well as TIF. Our band controls *precision*
comparability; TCC alignment is the stronger criterion for *score* comparability
across per-examinee forms. We already measure TCC spread post hoc (L2b); offering
it as an assembly-time band alongside TIF is a natural extension of the same
machinery.

### G5 — Small items

- **Item/option order randomization** per session (Luecht & Sireci security
  method (i)) — currently forms deliver in a fixed order.
- **§4.4 record persistence** — records are returned/carried in session state but
  not DB-persisted; the spec says persist. Lands naturally with Sessions.
- **Oracle-parity caveat** (TestDesign): band-feasibility ≠ minimax-optimality —
  any future LOFT-vs-TestDesign parity gate must compare *feasibility within
  band*, never objective values.
- **Pretest embedding** (ATS `PRE>`): n unscored pilot items per operational
  form — the classic operational alternative to our whole-form field-study path;
  worth adding to linear/LOFT assembly when the field study design firms up.
- **Testlets/sets** — absent platform-wide; TestDesign models them fully
  (stimulus-level variables/exposure). Already on the long-term list.

## 3. Recommended order

1. **G1 simulation harness** — unblocks honest claims about the whole platform
   (answers "do linear/LOFT have CAT-grade simulation?" with yes), and is the
   precondition for measuring G3.
2. **G2 engine (c)** — small, composes existing machinery, adds the QC-preferred
   operational variant.
3. **G3** exposure maturity (measure first via G1, then adopt fading eligibility
   if needed).
4. **G4/G5** as capacity allows; testlets/pretest with their upstream data
   dependencies.

*Working notes with full per-paper extractions: session scratchpad
(`loft_review_notes.md`); reader-agent reports quoted verbatim passages with
page/section markers.*
