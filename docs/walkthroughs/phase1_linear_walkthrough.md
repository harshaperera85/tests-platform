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
serves on :8000), `scoring-r` (stub), and `frontend` (Vite dev server on :5173). Wait
until you see the backend log `Uvicorn running on http://0.0.0.0:8000` and the frontend
log `VITE … ready`.

### Tunnel the ports (from your laptop)

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 <user>@<ec2-host>
```

Keep that session open. Then open in your browser:

| URL | What |
|---|---|
| http://localhost:5173 | **Frontend** — the Test Editor app (A-031 → A-033 → walkthrough) |
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

## The fixture pool (what your blueprints can ask for)

Until the item-factory export is wired, assembly runs against
`small_2pl_bank.json` — **48 calibrated 2PL items**, canonical metric (mirt `D=1.702`).
Tag counts you can constrain on:

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

## 1. Blueprint editor + assemble (A-031 Test Editor → Assembly)

Open **http://localhost:5173**. The editor loads pre-filled with a **known-feasible**
blueprint (this is the default):

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
- A blue "OR-Tools CP-SAT solving…" pill appears briefly, then the app advances to the
  **Form preview** screen (no error pill).
- (This blueprint is verified: status `optimal`, objective `0.000`, actual TIF exactly
  `8.0 / 11.0 / 8.0`.)

**FAIL** if you get a red warn pill, a spinner that never resolves, or a blank screen.

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
# the simulated item bank: params + tags + synthetic content + provenance
curl -s $BASE/pool/items | python3 -c 'import sys,json;d=json.load(sys.stdin);print("simulated",d["simulated"],"n",d["n_items"],"KC",d["tag_summary"]["KC"])'

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
