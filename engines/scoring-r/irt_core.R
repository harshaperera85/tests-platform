# Core IRT estimation functions for scoring-r (Analysis-module seed).
# Canonical metric throughout (CLAUDE.md golden rule 4): logistic D=1,
# slope-intercept (a, d); b = -d/a is a derived difficulty view. mirt 1.46.1
# is the single source of truth for joint estimation and covariances.
#
# Sourced by plumber.R (endpoints) AND calibrate_update_selftest.R (build-time
# verification) — one implementation, verified at image build.

library(mirt)

# ---- joint calibration ------------------------------------------------------
# long: data.frame(person, item, u) with u in {0,1}; structurally missing
# entries simply absent (booklet designs OK — MML marginalizes).
# Returns per-item canonical params + covariance elements + HONEST convergence.
fit_joint <- function(long, itemtype = "2PL", ncycles = 4000) {
  wide <- reshape(long, idvar = "person", timevar = "item", direction = "wide")
  rownames(wide) <- wide$person
  wide$person <- NULL
  colnames(wide) <- sub("^u\\.", "", colnames(wide))
  mat <- as.matrix(wide)
  # Drop near-degenerate items (any response category observed < 5 times) with
  # report — this covers mirt's hard error on single-category items and also
  # items too sparse for a stable 2PL fit.
  minc <- apply(mat, 2, function(x) min(table(factor(x, levels = 0:1))))
  dropped <- colnames(mat)[minc < 5]
  mat <- mat[, minc >= 5, drop = FALSE]
  fit <- mirt(mat, 1, itemtype = itemtype, SE = TRUE, verbose = FALSE,
              technical = list(NCYCLES = ncycles))
  co <- coef(fit, printSE = TRUE)       # slope-intercept (a1, d): canonical
  items <- setdiff(names(co), "GroupPars")
  vc <- vcov(fit)
  pn <- rownames(vc)
  # mirt orders free parameters item-block-wise: (a1, d) per item for 2PL.
  a_idx <- which(startsWith(pn, "a1."))
  d_idx <- which(startsWith(pn, "d."))
  stopifnot(length(a_idx) == length(items), length(d_idx) == length(items))
  rows <- lapply(seq_along(items), function(k) {
    p <- co[[items[k]]]
    list(item = items[k],
         a = unname(p["par", "a1"]), d = unname(p["par", "d"]),
         se_a = if ("SE" %in% rownames(p)) unname(p["SE", "a1"]) else NA,
         se_d = if ("SE" %in% rownames(p)) unname(p["SE", "d"]) else NA,
         var_a = unname(vc[a_idx[k], a_idx[k]]),
         var_d = unname(vc[d_idx[k], d_idx[k]]),
         cov_ad = unname(vc[a_idx[k], d_idx[k]]))
  })
  list(items = rows,
       dropped = as.list(dropped),
       convergence = list(converged = extract.mirt(fit, "converged"),
                          n_persons = nrow(mat), n_items = ncol(mat)),
       metric = list(scaling_d = 1, form = "slope-intercept",
                     kind = "calibrated"))
}

# ---- EAP person scoring under fixed params ---------------------------------
# params: data.frame(item, a, d); responses: data.frame(item, u)
eap_score <- function(params, responses, grid = seq(-6, 6, length.out = 121)) {
  m <- merge(responses, params, by = "item")
  z <- outer(rep(1, length(grid)), m$d) + outer(grid, m$a)   # d + a*theta
  p <- plogis(z)
  um <- matrix(rep(m$u, each = length(grid)), nrow = length(grid))
  ll <- rowSums(um * log(p) + (1 - um) * log(1 - p))
  post <- ll + dnorm(grid, log = TRUE)
  w <- exp(post - max(post)); w <- w / sum(w)
  th <- sum(w * grid)
  list(theta = th, se = sqrt(sum(w * (grid - th)^2)), n_items = nrow(m),
       metric = list(scaling_d = 1))
}

# ---- fixed-a per-item difficulty update (refinement-loop workhorse) --------
# Grid posterior over d with a FIXED (a is a supplied constant, not estimated,
# so the difficulty view's SE maps exactly: se_b = se_d / a — no delta method
# needed; this is the sanctioned synthetic-pool b = -d/a route WITH a valid SE
# because the posterior is computed, not propagated).
# prior: list(mu_d, sd_d)  [or mu_b/sd_b, converted internally via fixed a]
update_item <- function(a, responses, prior,
                        grid_d = NULL) {
  if (!is.null(prior$mu_b)) {
    prior$mu_d <- -a * prior$mu_b
    prior$sd_d <- a * prior$sd_b
  }
  if (is.null(grid_d)) {
    grid_d <- seq(prior$mu_d - 8 * prior$sd_d, prior$mu_d + 8 * prior$sd_d,
                  length.out = 241)
  }
  lp <- dnorm(grid_d, prior$mu_d, prior$sd_d, log = TRUE)
  for (i in seq_len(nrow(responses))) {
    p <- plogis(a * responses$theta[i] + grid_d)
    lp <- lp + if (responses$u[i] == 1) log(p) else log(1 - p)
  }
  w <- exp(lp - max(lp)); w <- w / sum(w)
  d_hat <- sum(w * grid_d)
  se_d <- sqrt(sum(w * (grid_d - d_hat)^2))
  list(a = a, d = d_hat, se_d = se_d,
       b = -d_hat / a, se_b = se_d / a,          # exact for fixed a
       n_responses = nrow(responses),
       metric = list(scaling_d = 1, form = "slope-intercept",
                     kind = "posterior-fixed-a"))
}

# ---- scale-linking diagnostics ----------------------------------------------
# set_x, set_y: data.frame(item, a, d) on putatively linkable scales.
link_stats <- function(set_x, set_y) {
  m <- merge(set_x, set_y, by = "item", suffixes = c("_x", "_y"))
  if (nrow(m) < 3) return(list(error = "need >=3 common items", n_common = nrow(m)))
  bx <- -m$d_x / m$a_x; by <- -m$d_y / m$a_y
  list(n_common = nrow(m),
       r_a = cor(m$a_x, m$a_y), r_d = cor(m$d_x, m$d_y), r_b = cor(bx, by),
       mean_shift_b = mean(by - bx),
       sd_ratio_b = sd(by) / sd(bx),
       metric = list(scaling_d = 1))
}
