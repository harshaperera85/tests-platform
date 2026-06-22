# Assembly oracle (DEV/TEST ONLY) — parity check for the owned OR-Tools engine.
#
# Reads a compiled ATA problem (JSON, emitted by r_oracle.py), solves it with an R
# oracle package (eatATA) and prints the selection + minimax objective as JSON on
# stdout. GPL packages — oracle only, never shipped (CLAUDE.md golden rule 2).
#
# Usage:  Rscript ata_oracle.R <problem.json> <package>
#   <package> currently supports "eatATA".
#
# Provision (outside the runtime image): R + jsonlite + eatATA + a MILP solver
# (lpSolve, or GLPK via Rglpk + system libglpk). The solver is auto-selected.

suppressMessages({
  library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
# simplifyVector=TRUE makes `info` an (nItems x nPoints) matrix and `enemy_pairs`
# an (nPairs x 2) matrix directly — use them as-is (do NOT unlist+reshape).
problem <- fromJSON(args[1], simplifyVector = TRUE)
package <- if (length(args) >= 2) args[2] else "eatATA"

info     <- problem$info
n_items  <- length(problem$item_ids)
stopifnot(is.matrix(info), nrow(info) == n_items)
n_points <- ncol(info)
target   <- as.numeric(problem$target_info)
method   <- problem$method

# Try solvers in order of preference; lpSolve needs no system libs.
solve_with_available <- function(constraints) {
  for (slv in c("lpSolve", "GLPK", "Symphony")) {
    res <- tryCatch(eatATA::useSolver(constraints, solver = slv),
                    error = function(e) NULL)
    if (!is.null(res) && isTRUE(res$solution_found)) {
      res$.solver <- slv
      return(res)
    }
  }
  stop("no available MILP solver succeeded (tried lpSolve, GLPK, Symphony)")
}

solve_eatATA <- function() {
  suppressMessages(library(eatATA))

  # Length: exactly L items in the single form.
  cons <- list(eatATA::itemsPerFormConstraint(
    1, nItems = n_items, operator = "=", targetValue = problem$length))

  # Content: lb/ub on tagged subsets.
  cs <- problem$content_sets
  if (!is.null(cs) && length(cs) > 0 && !is.null(nrow(cs))) {
    for (r in seq_len(nrow(cs))) {
      members <- unlist(cs$members[r]); sel <- rep(0, n_items); sel[members] <- 1
      lo <- cs$minimum[r]; hi <- cs$maximum[r]
      if (!is.na(lo)) cons <- c(cons, list(
        eatATA::itemValuesConstraint(1, sel, operator = ">=", targetValue = lo)))
      if (!is.na(hi)) cons <- c(cons, list(
        eatATA::itemValuesConstraint(1, sel, operator = "<=", targetValue = hi)))
    }
  }

  # Enemies: at most one of each pair.
  ep <- problem$enemy_pairs
  if (!is.null(ep) && length(ep) > 0) {
    if (!is.matrix(ep)) ep <- matrix(ep, ncol = 2, byrow = TRUE)
    for (r in seq_len(nrow(ep))) {
      sel <- rep(0, n_items); sel[ep[r, ]] <- 1
      cons <- c(cons, list(
        eatATA::itemValuesConstraint(1, sel, operator = "<=", targetValue = 1)))
    }
  }

  # Minimax TIF objective: one term per theta point. eatATA shares a single
  # deviation variable across them, giving a true min over max_k |TIF_k - t_k| —
  # the same objective as the owned CP-SAT model.
  for (k in seq_len(n_points)) {
    cons <- c(cons, list(eatATA::minimaxObjective(1, info[, k], target[k])))
  }

  res <- solve_with_available(cons)
  list(items = which(round(res$solution[seq_len(n_items)]) == 1),
       solver = res$.solver)
}

result <- tryCatch({
  if (package != "eatATA") stop(sprintf("oracle package %s not supported", package))
  out <- solve_eatATA()
  tif <- colSums(info[out$items, , drop = FALSE])
  objective <- if (method == "minimax") max(abs(tif - target)) else min(tif)
  list(status = "optimal", objective = objective,
       item_ids = problem$item_ids[out$items], solver = out$solver)
}, error = function(e) {
  list(status = "error", message = conditionMessage(e))
})

cat(toJSON(result, auto_unbox = TRUE, digits = 12))
