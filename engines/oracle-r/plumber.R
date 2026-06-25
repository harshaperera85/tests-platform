# Runtime ATA validation service (GPL oracle: eatATA + lpSolve).
#
# Read-only psychometric cross-validation: given a compiled ATA problem (the
# canonical D=1 info matrix + constraints + objective, serialized by the backend),
# solve it with eatATA and return the selection + objective. This is NEVER used to
# build a deliverable form — OR-Tools is the sole production assembler. Kept as a
# SEPARATE service from the mirt scoring-r so the GPL oracle stays isolated /
# re-firewallable (CLAUDE.md golden rule 2).
#
# Reuses the shared solver core copied from the backend tree.

suppressMessages(library(jsonlite))
source("/srv/oracle/ata_oracle_core.R")

#* Liveness check
#* @get /health
#* @serializer unboxedJSON
function() {
  list(
    status = "ok",
    service = "oracle-r",
    role = "ata-cross-validation",
    packages = list(
      eatATA = as.character(packageVersion("eatATA")),
      lpSolve = as.character(packageVersion("lpSolve"))
    )
  )
}

#* Cross-validate a compiled ATA problem with eatATA (read-only).
#* Body = the serialized CompiledProblem (info matrix, constraints, objective).
#* @post /assemble
#* @serializer unboxedJSON
function(req) {
  problem <- fromJSON(req$postBody, simplifyVector = TRUE)
  pkg <- if (!is.null(problem$package)) problem$package else "eatATA"
  t0 <- proc.time()[["elapsed"]]
  out <- oracle_solve(problem, pkg)
  out$solve_time_s <- proc.time()[["elapsed"]] - t0
  out
}
