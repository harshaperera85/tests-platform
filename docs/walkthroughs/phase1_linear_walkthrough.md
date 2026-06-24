# Phase 1 — Linear end-to-end operational walkthrough

A hands-on script to **drive the platform as built** and verify it operates correctly —
not just trust green CI. Covers the delivered linear capabilities: blueprint editor →
assemble → form preview (actual-vs-target TIF plot) → step-through navigator (real
engine via `/preview`).

> Generated from the actual current code: endpoints in `backend/app/api/v1/`, screens in
> `frontend/src/screens/tests/`, and the fixture pool
> `backend/app/psychometrics/fixtures/small_2pl_bank.json`. If those change, re-derive.

Everything below is reached **over your SSH tunnel** to the EC2 dev instance — the stack
binds to the instance's localhost; you forward the ports to your laptop.

---

## 0. Bring the stack up

On the instance (repo root `/home/ubuntu/tests-platform`):

```bash
docker compose -f infra/docker-compose.yml up --build
# or detached:  docker compose -f infra/docker-compose.yml up --build -d
```

This starts `postgres`, `redis`, `backend` (FastAPI, applies Alembic migrations then
serves on :8000), `worker` (RQ — runs assembly solves off the request), `scoring-r`
(stub), and `frontend` (Vite dev server on :5173). Wait until you see the backend log
`Uvicorn running on http://0.0.0.0:8000`, the worker log `Worker … listening on
assembly`, and the frontend log `VITE … ready`.

> **Assembly is asynchronous** in compose (`ASSEMBLY_ASYNC=true`): **Assemble**
> enqueues the solve and returns a **queued** job; the `worker` runs it and the job
> moves `queued → running → optimal/feasible` (or `infeasible`). The UI polls and
> shows "Assembling… (running)" until it's done. (Without a worker, set
> `ASSEMBLY_ASYNC=false` to solve inline.)

### Tunnel the ports (from your laptop)

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 <user>@<ec2-host>
```

Keep that session open. Then open in your browser:

| URL | What |
|---|---|
| http://localhost:5173 | **Frontend** — Test List (A-030) → Test Editor tabs (A-031..034) → walkthrough |
| http://localhost:8000/docs | **Swagger UI** — try the API directly |
| http://localhost:8000/openapi.json | OpenAPI contract (source of the generated client) |

> The browser only strictly needs **5173** for the UI: the frontend calls `/api/*`
> same-origin and the Vite dev server proxies to the backend inside the docker network.
> Tunnel **8000** too so you can open `/docs` and run the raw-API steps below.

Health check (over the tunnel):
```bash
curl -s http://localhost:8000/api/v1/health
# -> {"status":"ok","service":"tests-platform","version":"0.1.0","environment":"development"}
```
**Checkpoint 0 — PASS** if both URLs load and health returns `status: ok`.

---

## The simulated pools (what your blueprints can ask for)

Until the item-factory export is wired, the platform ships two **simulated** banks,
selectable in the editor (and via `GET /api/v1/pool/catalog`):

| Pool id | Items | Notes |
|---|---|---|
| `small_2pl` | 48 | 2PL only, single domain (`math`) — minimal smoke bank. |
| `demo_mixed` | 252 | **Default in the UI.** 3 domains (math/science/ela), 2PL **+ 79 3PL** items, wide symmetric difficulty, multi-item enemy sets — exercises every linear use case. |

The **`demo_mixed`** bank is what makes multi-domain balancing, guessing (3PL),
extreme cut scores, and several parallel forms + exposure demonstrable. The tables
below describe **`small_2pl`** (used by the §1 default + the §5 curl examples); the
demo bank's tag values differ per domain (e.g. KC `algebra/geometry/number/data`,
`biology/chemistry/physics/earth`, `reading/writing/grammar/vocab`).

### `small_2pl` tag counts
| Tag dimension | Values (count each) |
|---|---|
| `KC` | algebra (12), geometry (12), number (12), data (12) |
| `Bloom` | remember (16), apply (16), analyze (16) |
| `TIMSS` | number (12), algebra (12), geometry (12), data (12) |
| `domain` | math (48) |

Enemy pairs in the bank: **I001↔I002** and **I011→I012** (the engine symmetrizes the
second). Whole-pool TIF ≈ **21.9 / 30.3 / 22.1** at θ = −1 / 0 / 1 — so a 20-item form
can comfortably hit a target around 8–12 information.

---

## Navigation (the IA)

The app uses real routes, **server-backed by the `tests` resource** (`/api/v1/tests`):
- **`/`** — **Test List (A-030)**: tests persisted in the database. **+ New test**
  creates one (`POST /tests`) and opens its editor.
- **`/tests/:id/assembly`** — **Test Editor**, with tabs **Assembly (A-031)**,
  **About (A-032)**, **Scoring (A-034)**, **History (A-033)**. Deep links work on
  refresh. The editor's **Save draft** persists the blueprint (`PATCH /tests/{id}`);
  **Assemble** snapshots the draft and runs the engine (`POST /tests/{id}/assemble`).
- The editor header has **Lock / Unlock / Duplicate** (status workflow).
- **`/tests/:id/walk/:formId`** — the step-through walkthrough, reachable from the
  Assembly preview, the Scoring tab, or History.
- **`/pool`** — **Item pools** viewer (header nav): browse the simulated bank(s) —
  IRT params, tags, content — with a filter. Use this to *see the demo data*.

> A "test" owns an editable blueprint draft + its assembled forms (history), all
> persisted server-side — drafts survive refresh and are visible across browsers.

### Content constraints — marginal vs. joint, count vs. proportion

A content constraint bounds how many items in the form match a **tag predicate**:
- **Marginal** (one tag): `where KC = algebra` — controls a single dimension's total,
  independent of the others.
- **Joint / cross-classified cell** (click **+ AND tag**): `where KC = algebra AND
  Bloom = apply` — an item must match **all** predicates; this controls a cell of the
  content × cognitive table.

Each constraint's **min/max** is read as a **count** (absolute items) or a
**proportion** (0–1 of the form length, resolved to a count at assembly, nearest
integer). You can mix marginals, joint cells, counts, and proportions freely in one
blueprint.

**Why the distinction matters (feasibility), grounded in `demo_mixed`:** margins are
large but cells are thin, so joint constraints are much tighter than marginals.

| Bucket | Available items (demo_mixed) | Practical min you can ask for |
|---|---|---|
| `domain = math` (marginal) | 84 | large (e.g. 10, or 50% of the form) |
| `KC = algebra` (marginal) | 21 | comfortable (e.g. 6) |
| `Bloom = apply` (marginal) | ~51 | comfortable |
| `KC = algebra AND Bloom = apply` (**cell**) | **4** | **≤ 4** (≥5 is infeasible) |
| `domain = math AND Bloom = apply` (coarser cell) | 17 | up to ~17 |

So: use **marginals** for independent per-dimension targets; use **joint cells** when the
blueprint is a two-way table — but size each cell min to the items that exist (KC×Bloom
cells hold only ~4), keep the **sum of cell minimums ≤ form length**, and prefer a
**coarser** pairing (e.g. domain×Bloom) or a **proportion** when you need a larger joint
requirement.

#### Worked examples (all verified against `demo_mixed`, length 24, target 7/9/7)
1. **Marginal (feasible):** `KC=algebra ≥ 6` **and** `Bloom=apply ≥ 6` → `optimal`. Two
   independent margins; the same item can count toward both.
2. **Joint cell (feasible):** `KC=algebra AND Bloom=apply ≥ 3` **and** marginal
   `Bloom=analyze ≥ 4` → `optimal`. The cell has 4 items, so a min of 3 fits.
3. **Joint cell (infeasible — the ceiling):** `KC=algebra AND Bloom=apply ≥ 5` →
   **`infeasible`** (only 4 such items exist). This is the realistic failure to expect
   when a cell min exceeds the bank's cell size.
4. **Proportion (feasible):** `domain=math ≥ 0.5` (proportion) on a length-20 form →
   `optimal` (resolves to ≥ 10 math items).
5. **Coarser joint (feasible, roomier):** `domain=math AND Bloom=apply ≥ 6` → `optimal`
   (that cell holds ~17 items).

The TIF target is rarely the binding constraint here: whole-pool information is ≈
71 / 90 / 90 / 114 / 69 at θ = −2…2, so a 20–30 item form meets targets of ~7–12 (even
~30) easily; difficulty spread is wide (≈51 easy / 43 central / 54 hard items), which
supports cut-score targets anywhere on θ.

> Rule of thumb: if assembly comes back **infeasible** with joint cells, first check that
> each cell min ≤ the items in that cell (browse it in **Item pools**), then that the cell
> minimums sum to ≤ the form length.

## Field reference — what every control means

### Pool & scenario (top of the Assembly tab)
- **Item pool** — the calibrated bank assembly draws from. `demo_mixed` (252 items, 3
  domains, 2PL+3PL) or `small_2pl` (48, single-domain smoke bank). Stored on the test;
  the form's items are resolved against this pool everywhere downstream.
- **Demo scenario** — a one-click preset that **overwrites** the whole blueprint (pool,
  length, constraints, TIF target). A convenience starting point; edit freely after.

### Blueprint card
- **Name** — the test's display name (shows in the Test List / About).
- **Length** — items **per form**. With parallel forms, each form has this many.
- **Parallel forms** — how many psychometrically-parallel forms to assemble in one job
  (each matches the same TIF target). `1` = a single form.
- **Max use / item** — exposure cap: the most forms any one item may appear in across the
  job. Blank = unlimited. Only meaningful with parallel forms (e.g. `1` = no overlap).

### Content constraints (each row)
- **where `tag_type` = `tag_value`** — the predicate. `tag_type` is the tag **dimension**
  (`KC`, `Bloom`, `TIMSS`, `domain`); `tag_value` is the required value (`algebra`,
  `apply`, …). Browse valid values in **Item pools**.
- **+ AND tag** — add another predicate to the *same* constraint → a **joint cell** (item
  must match all). One predicate = a marginal.
- **min / max** — lower/upper bound on matching items. Either may be left blank.
- **count / proportion** — how min/max are read: absolute item counts, or a fraction
  (0–1) of the form length resolved to a count at assembly.
- **Remove** — delete the constraint. **+ Add constraint** (card header) adds a new one.

### Statistical target (TIF) card
- **Theta points** — the θ (ability) locations where you care about measurement
  precision, comma-separated (e.g. `-1, 0, 1`). θ is on the canonical metric.
- **Target info** — desired **test information** at each θ (same count as theta points).
  Higher = more precise (lower SE) there. Compare to the pool's envelope (see above).
- **Method** — **minimax**: drive actual TIF onto the target, minimizing the worst-point
  absolute miss (use for parallel/equated forms). **maximin**: maximize information at the
  weakest θ (use for a mastery/cut-score test; `target_info` acts as a reference/floor).
- **Tolerance** — optional hard band: forces `|actual − target| ≤ tolerance` at each θ in
  addition to the objective. Blank = objective only.

### Actions (bottom of the editor)
- **Assemble form** — saves the draft, then runs the engine (async): you'll see
  **queued → running**, then the form preview. Disabled while fields are invalid.
- **Save draft** — persist the blueprint without assembling (server-side; survives
  refresh). Shows a "saved …" pill.
- Inline cues: red field hints (validation), "Fix the highlighted fields", an
  **infeasible** (amber) vs **request failed/error** (red) vs **warnings** (blue) banner.

### Editor header (status workflow)
- **Lock** — freeze the test (read-only; blocks edit + re-assemble). Requires ≥1 form.
- **Unlock** — back to draft/editable. **Duplicate** — copy to a new draft test.
- **Tabs** — Assembly (A-031, editor+preview), About (A-032, identity + blueprint
  summary), Scoring (A-034, the EAP/canonical model), History (A-033, assembled forms).

### Form preview
- **worst |actual − target|** badge (green < 0.5) and **method** / **tolerance** pills.
- **TIF chart** — dense **actual** information curve over θ ∈ [−3, 3] (server-computed)
  with **target** points; a shaded band if a tolerance is set.
- **per-θ table** — target / actual / gap at each blueprint θ.
- **Content constraints** card — ✓/✗ per constraint with the count in the form vs the
  required bound (proportion bounds shown resolved, tagged `·prop`).
- **Assembled items** — the fixed linear order with each item's stem + `a`/`b` + KC/Bloom.
- **Walk the form →** opens the session navigator.

### Session navigator (Walk)
- **Manual / Simulated examinee** toggle.
- **Manual** — presents each item (with stem); **Answer correct / incorrect**; a live
  **θ̂ trace** + θ̂/SE pills update after each response (real EAP via `/preview`).
- **Simulated examinee** — **True θ** + **Seed**, then **Run**: the server simulates the
  whole session (2PL model) and plots θ̂ converging toward the dashed true-θ line, with a
  final θ̂/SE. Same seed → identical run.

### Item pools viewer (`/pool`)
- **Pool selector** (catalog), **filter** (id / stem / tag), and a table of every item's
  `a` / `b` / `c` and KC / Bloom / domain. Use it to see the data and to check cell sizes
  before writing joint constraints.

## 1. Blueprint editor + assemble (Test Editor → Assembly tab, A-031)

Open **http://localhost:5173** → **Test List**. Click **+ New test**, which opens the
**Assembly** tab. At the top, **Pool & scenario**:
- **Item pool** — defaults to `demo_mixed` (252 items). You can switch to `small_2pl`.
- **Demo scenario** — a dropdown of curated presets (`GET /api/v1/scenarios`). Selecting
  one **populates the whole blueprint + pool** in one click. Use these to exercise each
  capability deliberately:
  - `multi_domain` — equal math/science/ela coverage (10/10/10).
  - `mastery_cut` — maximin information at a high cut score (θ = 1.5).
  - `parallel_exposure` — **3 parallel forms**, each item used at most once.
  - `guessing_3pl` — reasoning-heavy form drawn from 3PL items.
  - `infeasible_demo` — the deliberate failure case (see §4).

For the baseline, leave the default (or load `smoke_small` for the small bank). The
editor is pre-filled with a **known-feasible** blueprint:

| Field | Value |
|---|---|
| Name | `linear-demo` |
| Length | `20` |
| Content constraints | `KC algebra` min 4 max 8 · `KC geometry` min 4 · `Bloom analyze` min 3 |
| Theta points | `-1, 0, 1` |
| Target info | `8, 11, 8` |
| Method | `minimax` |
| Tolerance | (blank) |

Click **Assemble form**.

**Checkpoint 1 — PASS** if:
- An "Assembling…" spinner shows the job status (`queued` → `running`) while the worker
  solves, then the **Form preview** appears below the editor (no error pill). For small
  blueprints this is a second or two.
- (On `small_2pl` this is verified: status `optimal`, objective `0.000`, actual TIF
  exactly `8.0 / 11.0 / 8.0`. On `demo_mixed` it also assembles `optimal` with different
  items.)

**FAIL** if you get a red warn pill, a spinner that never resolves, or a blank screen.

**Checkpoint 1b (scenarios) — PASS** if loading each preset and clicking **Assemble form**
behaves as its note says:
- `multi_domain` → preview's **Content constraints** card shows math/science/ela each ✓ at
  exactly 10.
- `parallel_exposure` → the assembly job reports **3 forms** (the preview shows the first);
  verify zero overlap via the API in §5 if you wish.
- `guessing_3pl` → assembles `optimal`/`feasible` from the 3PL-bearing bank.
- `mastery_cut` → assembles; information concentrates near θ = 1.5 (visible in §2's curve).

---

## 2. Form preview + actual-vs-target TIF plot (A-033)

You should now see the **Form preview** screen.

**Checkpoint 2 — PASS** if:
- The header shows ~`Form <id> · 20 items · status draft`, plus a green
  **`worst |actual − target|`** badge (green when < 0.5) and a **`method: minimax`** pill.
- The **TIF chart** shows a smooth indigo **actual** curve (dense, computed server-side
  over θ ∈ [−3, 3] via `/forms/{id}/tif-curve`) with dark **target** points at θ = −1, 0, 1;
  the actual curve **sits on the target points** (≈ 8 / 11 / 8) and may rise higher between
  them. If a **tolerance** was set, a faint grey band is drawn around each target point.
- The **per-θ table** lists target / actual / gap; gaps are green when |gap| < 0.5.
- The **Content constraints** card shows a ✓/✗ per constraint with the actual count vs the
  required bounds (e.g. `KC=algebra 5 in form (need 4..8) ✓`).
- The **Assembled items** list shows 20 distinct ids **with simulated stems and params**
  (e.g. `I004  [SIMULATED · …]  (a=…, b=…, geometry/apply)`) — and must **not** contain
  both items of an enemy pair (no `I001`+`I002`, no `I011`+`I012`).

**Pass criterion:** *actual TIF tracks target within tolerance* (worst gap < 0.5; here
≈ 0), constraint badges all ✓. **FAIL** if the actual curve is far off the target points
while the badge claims a good fit, a constraint shows ✗, or the item list has the wrong
length / duplicates / an enemy pair.

---

## 3. Step-through navigator — real engine via `/preview`

Click **Walk the form →**. The navigator drives the actual `LinearStrategy` through the
thin `/api/v1/preview` endpoint; the server is stateless and θ/SE are the engine's real
**EAP** estimate. It has two modes (toggle buttons top-right): **Manual** and
**Simulated examinee**.

### 3a. Manual mode — answer with a live θ̂ trace
Each presented item shows its **simulated stem**. After every answer the app re-scores
(`/preview/score`) and updates a **live θ̂ trace** chart and the θ̂ / SE pills.

- **Run A — all correct:** click **Answer correct** for all 20. **PASS** if θ̂ climbs to
  **clearly positive** (~+1 to +2.5), the trace rises, and **SE drops well below 1.0**
  (~0.3–0.4) by the end.
- **Run B — all incorrect:** **← Back to preview**, walk again, **Answer incorrect** ×20.
  **PASS** if θ̂ is **clearly negative** (mirror of Run A).

**Pass criterion:** *θ̂ rises on correct answers and falls on incorrect ones, and SE
shrinks below the prior (1.0) as items accumulate.* **FAIL** if θ̂ stays ~0 regardless of
answers, SE stays ~1.0, the item count desyncs, or scoring errors out.

### 3b. Simulated examinee — genuine simulated e2e (no manual input)
Switch to **Simulated examinee**. Enter a **True θ** (try `2.0`, then `-1.5`) and a seed,
click **Run simulated examinee**. The server simulates the whole session (real engine +
2PL response model on the canonical metric) and returns the θ̂ trace + final estimate.

**Checkpoint 3b — PASS** if the θ̂ trace **converges toward the dashed true-θ line** and
the final θ̂ lands near the true θ with SE ~0.3–0.4 (e.g. true 2.0 → θ̂ ≈ 1.7; true −2.0 →
θ̂ ≈ −1.4). Re-running with the **same seed** is identical; a different seed varies
slightly. **FAIL** if the trace ignores the true θ or the estimate is on the wrong side.

> This is a dry run — stems are synthetic simulated content; correctness in the simulator
> is drawn from the 2PL model at the true θ, not from any literal answer key.

---

## 4. Deliberately **infeasible** blueprint (see failure behavior)

Go back to the editor (**← Edit blueprint** from preview, or restart the flow). Set an
over-constrained blueprint that **cannot** be satisfied:

| Field | Value |
|---|---|
| Length | `20` |
| Content constraints | `KC algebra` **min 20 max 20** (delete the others) |
| Theta points | `0` |
| Target info | `5` |

Click **Assemble form**. (Only 12 `algebra` items exist, but the form demands 20 — the
solver cannot satisfy it.)

**Checkpoint 4 — PASS** if you get a **clear amber warn pill**:
`Assembly infeasible: no feasible form. Loosen constraints or TIF target.` — the app
stays on the editor and remains responsive.

**Pass criterion:** *infeasible blueprint returns a clear error, not a crash/hang.*
**FAIL** if the app crashes, shows a stack trace, spins forever, or silently advances to
an empty preview.

> Backend nuance: `POST /assembly-jobs` returns **HTTP 201** with `status: "infeasible"`
> and empty `form_ids` (it's a valid job outcome, not an HTTP error). The UI turns that
> into the warn pill.

---

## 5. (Optional) Verify the API directly — Swagger or curl

Independent of the UI, confirm the backend over the tunnel. In **http://localhost:8000/docs**
use "Try it out", or curl:

### 5a. Known-feasible blueprint → assemble → preview the form
```bash
BASE=http://localhost:8000/api/v1

BP=$(curl -s -X POST $BASE/blueprints -H 'content-type: application/json' -d '{
  "name":"linear-demo","length":20,
  "statistical_target":{"theta_points":[-1,0,1],"target_info":[8,11,8],"method":"minimax"},
  "content_constraints":[
    {"tag_type":"KC","tag_value":"algebra","minimum":4,"maximum":8},
    {"tag_type":"KC","tag_value":"geometry","minimum":4},
    {"tag_type":"Bloom","tag_value":"analyze","minimum":3}]}' )
BID=$(echo "$BP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

JOB=$(curl -s -X POST $BASE/assembly-jobs -H 'content-type: application/json' \
  -d "{\"blueprint_id\":\"$BID\",\"strategy\":\"mip\",\"time_limit_s\":8}")
echo "$JOB" | python3 -m json.tool        # expect status optimal|feasible, objective ~0, one form_id
FID=$(echo "$JOB" | python3 -c 'import sys,json;print(json.load(sys.stdin)["form_ids"][0])')

curl -s $BASE/forms/$FID | python3 -m json.tool   # item_ids (20) + tif: actual vs target per theta
```
**Expect:** `status` `optimal`/`feasible`; `tif` entries where `actual ≈ target` and
`gap ≈ 0`.

### 5b. Step through the engine
```bash
S=$(curl -s -X POST $BASE/preview/start -H 'content-type: application/json' -d "{\"form_id\":\"$FID\"}")
# repeat: read next_action.payload.item_id, POST it to /preview/respond with the carried-back state…
# then POST the final state to /preview/score -> theta, standard_error, scale=canonical
```
(The UI does this loop for you; the integration test
`backend/app/tests/integration/test_preview_api.py` is the canonical reference.)

### 5b′. Simulated-data endpoints (genuine demo data, no real export wired)
```bash
# catalog of selectable simulated banks
curl -s $BASE/pool/catalog | python3 -c 'import sys,json;d=json.load(sys.stdin);print("default",d["default_pool_id"]);[print(" ",p["pool_id"],p["n_items"],"items",p["n_3pl"],"3PL",p["domains"]) for p in d["pools"]]'

# curated demo scenarios (bank + blueprint presets)
curl -s $BASE/scenarios | python3 -c 'import sys,json;[print(" ",s["scenario_id"],"->",s["pool_id"]) for s in json.load(sys.stdin)]'

# the simulated item bank (select with ?pool_id=demo_mixed): params + tags + content
curl -s "$BASE/pool/items?pool_id=demo_mixed" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("pool",d["pool_id"],"simulated",d["simulated"],"n",d["n_items"],"domains",list(d["tag_summary"]["domain"]))'

# dense actual TIF over a theta grid (server-computed on the canonical metric)
curl -s "$BASE/forms/$FID/tif-curve?theta_min=-3&theta_max=3&n=61" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("curve points",len(d["curve"]),"method",d["method"],"tol",d["tolerance"])'

# simulated examinee at a known true theta (real engine + 2PL); estimate tracks truth
curl -s "$BASE/forms/$FID/simulate?theta=2.0&seed=1" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("true",d["true_theta"],"-> final theta_hat",round(d["final_theta"],3),"SE",round(d["final_standard_error"],3))'
```
**Expect:** `pool/items` → `simulated: true`, 48 items; `tif-curve` → 61 points;
`simulate` (θ=2.0) → `final_theta` clearly positive (~1.7).

### 5c. Infeasible vs invalid (two distinct failure modes)
```bash
# infeasible (solver): HTTP 201, status "infeasible", form_ids []
curl -s -X POST $BASE/blueprints -H 'content-type: application/json' -d '{
  "length":20,"statistical_target":{"theta_points":[0],"target_info":[5]},
  "content_constraints":[{"tag_type":"KC","tag_value":"algebra","minimum":20,"maximum":20}]}' \
  | python3 -c 'import sys,json;print("blueprint id:",json.load(sys.stdin)["id"])'
# …then POST that id to /assembly-jobs -> status "infeasible".

# invalid (schema): HTTP 422 — a content minimum greater than the form length is rejected
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/blueprints \
  -H 'content-type: application/json' -d '{
  "length":10,"statistical_target":{"theta_points":[0],"target_info":[5]},
  "content_constraints":[{"tag_type":"KC","tag_value":"algebra","minimum":11}]}'   # -> 422
```

---

## What to look for — genuine bugs vs. cosmetic polish

**Genuine bugs (block Phase 2 — record and report):**
- Assemble returns HTTP 5xx, or the UI crashes / white-screens.
- "optimal/feasible" but the **actual TIF is visibly far from target** (objective claims a
  good fit that the plot contradicts).
- Item list has the wrong length, duplicates, or **both items of an enemy pair**.
- Navigator **desyncs** (item count ≠ length, can't reach end, wrong item presented).
- θ̂ **doesn't respond** to answers (stays ~0 for all-correct and all-incorrect), or SE
  stays at 1.0, or `/preview/score` errors; the live trace doesn't move.
- **Simulated examinee** estimate lands on the wrong side of the true θ, or the trace
  doesn't converge toward the dashed true-θ line; same-seed runs differ.
- A **content-constraint badge shows ✗** on a form the engine called feasible (mismatch
  between solver and the displayed satisfaction check).
- Infeasible blueprint **crashes or hangs** instead of a clear message.

**Cosmetic polish (note, but not blocking):**
- Spacing/alignment, plot colors/legend/axis labels, button copy.
- No per-step URLs/deep links (single staged flow, no router — deferred IA expansion).
- The single JS bundle is ~660 kB (Recharts); acceptable for an internal tool.
- Simulated stems are templated placeholder text (real stems arrive with the
  item-factory export) — expected.

### Findings log

| # | Step / checkpoint | Observed | Bug or cosmetic? | Notes |
|---|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |

---

## Tear down

```bash
docker compose -f infra/docker-compose.yml down
# add -v to also drop the postgres volume (fresh DB next time)
```
