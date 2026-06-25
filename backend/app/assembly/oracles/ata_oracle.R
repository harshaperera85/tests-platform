# Assembly oracle CLI bridge (DEV/TEST) — parity check for the owned engine.
#
# Reads a compiled ATA problem (JSON, emitted by r_oracle.py), solves it via the
# shared core (ata_oracle_core.R) with eatATA, and prints the selection + minimax
# objective as JSON on stdout. GPL packages — oracle only, never shipped
# (CLAUDE.md golden rule 2). The runtime validation service reuses the same core.
#
# Usage:  Rscript ata_oracle.R <problem.json> <package>

suppressMessages(library(jsonlite))

# Source the shared core from this script's own directory (robust under Rscript).
.script_dir <- function() {
  a <- commandArgs(FALSE)
  f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f)) dirname(normalizePath(f)) else "."
}
source(file.path(.script_dir(), "ata_oracle_core.R"))

args <- commandArgs(trailingOnly = TRUE)
# simplifyVector=TRUE makes `info` an (nItems x nPoints) matrix directly.
problem <- fromJSON(args[1], simplifyVector = TRUE)
package <- if (length(args) >= 2) args[2] else "eatATA"

cat(toJSON(oracle_solve(problem, package), auto_unbox = TRUE, digits = 12))
