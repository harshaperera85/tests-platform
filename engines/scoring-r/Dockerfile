# Canonical mirt scoring service. Pins mirt 1.46.1 (the CAT platform's version) so
# the difficulty conversion's delta-method SE(b) is validated against mirt's own
# coef(IRTpars=TRUE) at build time (convert_difficulty_selftest.R fails the build on
# any mismatch). Endpoint runtime needs only jsonlite; mirt backs the validation.
FROM rstudio/plumber:latest

# System libs required to compile mirt's dependency chain (nanonext/fs/SimDesign).
RUN apt-get update && apt-get install -y --no-install-recommends \
      cmake libmbedtls-dev libuv1-dev libssl-dev libcurl4-openssl-dev \
      libxml2-dev libgit2-dev \
    && rm -rf /var/lib/apt/lists/*

RUN R -e "install.packages('remotes', repos='https://cloud.r-project.org')" \
 && R -e "remotes::install_version('mirt', version='1.46.1', repos='https://cloud.r-project.org', upgrade='never')"

WORKDIR /app
COPY plumber.R irt_core.R convert_difficulty_selftest.R calibrate_update_selftest.R /app/

# Fail the build if the delta-method SE(b) ever diverges from mirt's IRTpars SE(b),
# or if the Analysis-seed estimators (joint calibrate / EAP / fixed-a update /
# link) fail their recovery selftests.
RUN Rscript /app/convert_difficulty_selftest.R \
 && Rscript /app/calibrate_update_selftest.R

EXPOSE 8000
CMD ["/app/plumber.R"]
