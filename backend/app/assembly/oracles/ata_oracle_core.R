# Assembly oracle core (DEV/TEST + read-only runtime validation).
#
# Pure solve logic shared by the CLI bridge (ata_oracle.R, used by the CI parity
# test via r_oracle.py) and the runtime plumber service (engines/oracle-r). Given a
# compiled ATA problem (parsed JSON: the canonical D=1 info matrix + constraints +
# objective), it solves with the GPL R oracle package eatATA and returns the
# selected items + minimax objective. GPL — oracle/validation only, never used to
# build a deliverable form (CLAUDE.md golden rule 2).

suppressMessages({
  library(jsonlite)
})

# Try MILP solvers in order of preference; lpSolve needs no system libs.
.solve_with_available <- function(constraints) {
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

.solve_eatATA <- function(problem, info, n_items, n_points, target) {
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

  # Minimax TIF objective: one term per theta point sharing a single deviation
  # variable — the same min over max_k |TIF_k - t_k| as the owned CP-SAT model.
  for (k in seq_len(n_points)) {
    cons <- c(cons, list(eatATA::minimaxObjective(1, info[, k], target[k])))
  }

  res <- .solve_with_available(cons)
  list(items = which(round(res$solution[seq_len(n_items)]) == 1),
       solver = res$.solver)
}

# Solve a parsed problem (fromJSON simplifyVector=TRUE so `info` is a matrix).
# Returns a list(status, objective, item_ids, solver) — or status="error".
oracle_solve <- function(problem, package = "eatATA") {
  info     <- problem$info
  n_items  <- length(problem$item_ids)
  stopifnot(is.matrix(info), nrow(info) == n_items)
  n_points <- ncol(info)
  target   <- as.numeric(problem$target_info)
  method   <- problem$method

  tryCatch({
    if (package != "eatATA") stop(sprintf("oracle package %s not supported", package))
    out <- .solve_eatATA(problem, info, n_items, n_points, target)
    tif <- colSums(info[out$items, , drop = FALSE])
    objective <- if (method == "minimax") max(abs(tif - target)) else min(tif)
    list(status = "optimal", objective = objective,
         item_ids = problem$item_ids[out$items], solver = out$solver)
  }, error = function(e) {
    list(status = "error", message = conditionMessage(e))
  })
}
