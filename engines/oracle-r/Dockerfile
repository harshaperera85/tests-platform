# =============================================================================
# DEV / CI ONLY — assembly parity oracle image.  NEVER a runtime dependency.
#
# This image carries the GPL R oracle packages (eatATA, and Rglpk/GLPK) used to
# validate the owned OR-Tools assembly engine on fixtures (plan §6, §14). Per
# CLAUDE.md golden rule 2 these packages must stay out of every shipped/runtime
# image — they live here only, and only CI / local test runs use this image.
# The runtime scoring service is the separate, package-free engines/scoring-r/.
#
# Build (from repo root, so backend/requirements.txt is in context):
#   docker build -f engines/oracle-r/Dockerfile -t oracle-r:ci .
# Run the parity test (mount the backend source read-only style):
#   docker run --rm -v "$PWD/backend:/app" -w /app oracle-r:ci
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

# Backend source is mounted at /app at run time (kept out of the image so code
# changes don't bust the cached R/Python layers).
WORKDIR /app

# The plumber base sets an ENTRYPOINT that launches the R server; reset it so this
# image runs ordinary commands (pytest / Rscript) instead.
ENTRYPOINT []

# Default: run only the R-oracle parity test. cacheprovider disabled so pytest
# never writes into the mounted source tree.
CMD ["pytest", "app/tests/regression/test_oracle_parity.py::test_mip_matches_r_oracle", \
     "-q", "-p", "no:cacheprovider"]
