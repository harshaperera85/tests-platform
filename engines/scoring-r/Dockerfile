# Stub mirt scoring service for Phase 0. Uses the rstudio/plumber base (plumber
# preinstalled) so the image builds fast and returns a health response. Phase 1+
# adds mirt + the scoring endpoints.
FROM rstudio/plumber:latest

WORKDIR /app
COPY plumber.R /app/plumber.R

EXPOSE 8000

# Base image's entrypoint plumbs the given file and serves on 0.0.0.0:8000.
CMD ["/app/plumber.R"]
