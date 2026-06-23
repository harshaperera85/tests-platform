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
- The header shows ~`Form <id> · 20 items · status draft`.
- A green badge reads **`worst |actual − target| = 0.00x`** (tone is green when < 0.5).
- The **TIF chart** shows two lines over θ = −1, 0, 1: a dashed grey **target** and a
  solid indigo **actual** that **tracks the target** (both near 8 / 11 / 8). The actual
  line should sit essentially on top of the target.
- The **Assembled items** list shows 20 distinct item ids (e.g. `I004`, `I006`, …), and
  it must **not** contain both items of an enemy pair (no `I001`+`I002` together, no
  `I011`+`I012` together).

**Pass criterion:** *actual TIF tracks target within tolerance* (worst gap < 0.5; here
≈ 0). **FAIL** if the actual line is far off the target while the badge/objective claims
a good fit, or the item list has wrong length / duplicate or enemy-conflicting items.

---

## 3. Step-through navigator — real engine via `/preview`

Click **Walk the form →**. This drives the actual `LinearStrategy` through the thin
`/api/v1/preview` endpoint (`start` → `respond` → `score`); the server is stateless and
θ/SE are the engine's real **EAP** estimate.

Run it **twice** to see the score respond to input:

### Run A — answer every item **correct**
- Click **Answer correct** for all 20 items. The progress bar fills; the "item N / 20"
  pill advances.
- At the end you see **"End of form — end_of_form"**; click **Score session**.

**Checkpoint 3A — PASS** if θ (EAP, canonical) is **clearly positive** (roughly +1 to
+2.5) and **SE is well below 1.0** (the prior SD), e.g. ~0.3–0.5 — i.e. information was
gained from a full 20-item form.

### Run B — answer every item **incorrect**
- Go **← Back to preview**, then **Walk the form →** again. Click **Answer incorrect**
  for all 20.

**Checkpoint 3B — PASS** if θ is **clearly negative** (mirror of Run A).

**Pass criterion:** *θ rises on correct answers and falls on incorrect ones, and SE
shrinks below the prior (1.0) as items accumulate.* **FAIL** if θ stays ~0 regardless of
answers, SE stays ~1.0, the item count desyncs, or scoring errors out.

> Note: this is a dry run — items show only their ids (no real stem/options); you are
> simulating an examinee's correctness.

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
- θ **doesn't respond** to answers (stays ~0 for all-correct and all-incorrect), or SE
  stays at 1.0, or `/preview/score` errors.
- Infeasible blueprint **crashes or hangs** instead of a clear message.

**Cosmetic polish (note, but not blocking):**
- Spacing/alignment, plot colors/legend/axis labels, button copy.
- No loading spinner besides the pill; no inline field validation hints.
- No per-step URLs/deep links (single staged flow, no router).
- Vite "chunk larger than 500 kB" build warning (Recharts) — advisory only.
- Item list shows ids only (no stem/metadata) — expected; content isn't wired yet.

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
