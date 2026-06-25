# =============================================================================
# ATA validation oracle image — GPL R packages (eatATA + lpSolve), kept ISOLATED.
#
# Two roles, one image:
#   1. CI parity gate (default-overridden command runs pytest; see below).
#   2. Runtime READ-ONLY cross-validation service (default CMD = plumber on :8000),
#      called by the backend so users can validate an OR-Tools form against eatATA.
#
# The GPL oracle packages live ONLY in this image and are NEVER used to build a
# deliverable form — OR-Tools is the sole production assembler (CLAUDE.md golden
# rule 2). This service is deliberately SEPARATE from the package-free mirt
# scoring-r so the GPL oracle stays isolated / re-firewallable.
#
# Build (from repo root, so backend/* is in context):
#   docker build -f engines/oracle-r/Dockerfile -t oracle-r .
# CI parity test (overrides the default CMD, mounts backend source):
#   docker run --rm -v "$PWD/backend:/app" -w /app oracle-r \
#       pytest app/tests/regression/test_oracle_parity.py::test_mip_matches_r_oracle -q
# =============================================================================

# Same R base as the runtime scoring service (engines/scoring-r/) so the R
# toolchain matches. R package versions are pinned via a dated CRAN snapshot below.
FROM rstudio/plumber:latest

# --- system deps: Python (to run our engine + pytest) and GLPK (for Rglpk) ---
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip \
        libglpk-dev \
    && rm -rf /var/lib/apt/lists/*

# --- R oracle packages, pinned to a dated Posit Package Manager snapshot --------
# The snapshot date pins lpSolve / eatATA / Rglpk (+ deps) to reproducible
# versions; binaries are served for the base image's distro so no slow compile.
ARG CRAN_SNAPSHOT=2026-06-01
RUN . /etc/os-release \
    && Rscript -e "options(repos = c(P3M = sprintf('https://packagemanager.posit.co/cran/__linux__/%s/%s', '${VERSION_CODENAME}', '${CRAN_SNAPSHOT}'))); \
        install.packages(c('lpSolve', 'eatATA')); \
        stopifnot(requireNamespace('lpSolve', quietly = TRUE), requireNamespace('eatATA', quietly = TRUE)); \
        writeLines(c(paste('snapshot', '${CRAN_SNAPSHOT}'), \
                     paste('lpSolve', packageVersion('lpSolve')), \
                     paste('eatATA',  packageVersion('eatATA')), \
                     paste('Rglpk',   packageVersion('Rglpk'))), \
                   '/opt/oracle-r-versions.txt'); \
        cat(readLines('/opt/oracle-r-versions.txt'), sep = '\n')"

# --- Python deps: our backend's runtime requirements + pytest ------------------
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt pytest

# Runtime validation service: the plumber app + the shared solver core (copied
# from the backend tree so the runtime image is self-contained; the CI path uses
# the mounted backend copy instead).
COPY engines/oracle-r/plumber.R /srv/oracle/plumber.R
COPY backend/app/assembly/oracles/ata_oracle_core.R /srv/oracle/ata_oracle_core.R

# Backend source is mounted at /app for the CI parity run (kept out of the image so
# code changes don't bust the cached R/Python layers).
WORKDIR /app

# The plumber base sets an ENTRYPOINT that launches a server; reset it so the CI
# command override (pytest / Rscript) runs as an ordinary command.
ENTRYPOINT []

EXPOSE 8000

# Default: run the runtime read-only validation service. CI overrides this with an
# explicit `pytest ...` command (which runs instead of this CMD).
CMD ["Rscript", "-e", "plumber::pr_run(plumber::pr('/srv/oracle/plumber.R'), host='0.0.0.0', port=8000)"]
