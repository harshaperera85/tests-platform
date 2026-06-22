# oracle-r — assembly parity oracle (DEV / CI ONLY)

This image validates the **owned OR-Tools assembly engine** against the R
psychometric ATA packages (`eatATA`, with `lpSolve` / GLPK as the MIP solver) on
known fixtures — the automated form of plan §6 / §14's validation oracles.

## ⚠️ Never a runtime dependency

`eatATA` and `Rglpk`/GLPK are **GPL**. Per **CLAUDE.md golden rule 2**, assembly is
owned in Python and the R packages are *dev-time validation oracles only* — they
must never ship in, or be imported by, any runtime image or code path.

- **Runtime scoring service:** [`engines/scoring-r/`](../scoring-r) — `mirt`-based
  canonical θ metric, **no** ATA/oracle packages.
- **This image (`engines/oracle-r/`):** test/CI only. Built and run by the
  `oracle-parity` CI job and for local parity checks. Nothing in the application
  depends on it.

The backend's `app/assembly/oracles/` bridge (`r_oracle.py` + `ata_oracle.R`) lives
under `app/` for test discovery, but it is imported **only** by tests; the runtime
engine never touches `oracles/`.

## What's inside

- Base: `rstudio/plumber:latest` (same R toolchain as `scoring-r`).
- R packages pinned to a dated Posit Package Manager snapshot (`CRAN_SNAPSHOT`
  build arg, default `2026-06-01`): `lpSolve`, `eatATA` (+ `Rglpk`, `slam`).
  Installed versions are recorded at `/opt/oracle-r-versions.txt`.
- `libglpk-dev` so the GLPK solver is available (the oracle script auto-selects
  `lpSolve` first, then GLPK).
- Python 3 venv with the backend's `requirements.txt` + `pytest`, to run our
  OR-Tools engine and the parity assertion in the same container.

## Usage

```bash
# from the repo root (backend/requirements.txt must be in the build context)
docker build -f engines/oracle-r/Dockerfile -t oracle-r:ci .

# run the parity test against the live backend source
docker run --rm -v "$PWD/backend:/app" -w /app oracle-r:ci
```

The test (`test_mip_matches_r_oracle`) assembles the fixture with our engine **and**
with `eatATA`, then asserts (a) identical item selection and (b) objective agreement
within a tolerance tied to `INFO_SCALE`. On the fixture the expected result is the
form `T0, T2, T4, T5` with minimax objective ≈ 0.488 (ours, integer-scaled) vs
≈ 0.4879 (eatATA, continuous).
