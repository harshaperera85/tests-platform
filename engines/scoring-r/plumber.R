# Canonical scoring / IRT service (mirt). Single source of truth for the theta
# metric (CLAUDE.md golden rule 4): logistic D=1, slope-intercept (a, d).
#
# /convert-difficulty is the authoritative slope-intercept -> traditional (a, b)
# DIFFICULTY conversion. mirt is the source of truth: b and SE(b) are produced by
# mirt's own delta-method (mirt::DeltaMethod) applied to b = -d/a with the given
# parameter covariance — the same computation coef(IRTpars=TRUE) performs. The
# analytic Jacobian formula is kept ONLY as a build-time parity tripwire
# (convert_difficulty_selftest.R), never as the runtime computation.

library(jsonlite)
library(mirt)

#* Liveness check
#* @get /health
#* @serializer unboxedJSON list(digits = 15)
function() {
  list(
    status = "ok",
    service = "scoring-r",
    role = "canonical-theta-metric",
    metric = "logistic-D1-slope-intercept",
    mirt_version = as.character(packageVersion("mirt"))
  )
}

#* Convert slope-intercept (a, d) + parameter covariance to traditional (a, b)
#* with delta-method SE(b), computed by mirt::DeltaMethod (authoritative).
#* Body: {a, d, var_a, var_d, cov_ad}. b = -d/a.
#* @post /convert-difficulty
#* @serializer unboxedJSON list(digits = 15)
function(req) {
  body <- fromJSON(req$postBody)
  a <- as.numeric(body$a)
  d <- as.numeric(body$d)
  if (is.null(a) || is.null(d) || a <= 0) {
    return(list(error = "require a>0 and d"))
  }
  fn <- function(p) -p[2] / p[1]   # b = -d/a
  out <- list(a = a, b = fn(c(a, d)), se_b = NULL)
  if (!is.null(body$var_a) && !is.null(body$var_d)) {
    Va <- as.numeric(body$var_a)
    Vd <- as.numeric(body$var_d)
    Cad <- if (is.null(body$cov_ad)) 0 else as.numeric(body$cov_ad)
    acov <- matrix(c(Va, Cad, Cad, Vd), 2, 2)
    # mirt's own delta method propagates the (a,d) covariance through b = -d/a.
    res <- DeltaMethod(fn, c(a, d), acov)
    out$se_b <- as.numeric(res$se)
  }
  out
}

# ---------------------------------------------------------------------------
# Analysis-module seed (calibration engine P2): response-based estimation.
# One implementation (irt_core.R), verified at image build
# (calibrate_update_selftest.R). All outputs carry canonical metric
# declarations (golden rule 4); difficulty views come from the posterior
# (fixed-a route, exact SE) or from /convert-difficulty (calibrated route).
source("/app/irt_core.R")

#* Joint 2PL calibration (MML-EM via mirt) on person-level responses.
#* Body: {responses: [{person, item, u}], itemtype?}
#* Returns canonical (a, d) + SEs + covariance elements per item, dropped
#* items, and an HONEST convergence report.
#* @post /calibrate
#* @serializer unboxedJSON list(digits = 15)
function(req) {
  body <- fromJSON(req$postBody)
  long <- as.data.frame(body$responses)
  if (!all(c("person", "item", "u") %in% names(long))) {
    return(list(error = "responses must have person, item, u"))
  }
  itemtype <- if (is.null(body$itemtype)) "2PL" else body$itemtype
  fit_joint(long, itemtype = itemtype)
}

#* EAP person scoring under fixed canonical params.
#* Body: {params: [{item, a, d}], responses: [{item, u}]}
#* @post /score
#* @serializer unboxedJSON list(digits = 15)
function(req) {
  body <- fromJSON(req$postBody)
  eap_score(as.data.frame(body$params), as.data.frame(body$responses))
}

#* Fixed-a per-item difficulty update (the refinement-loop workhorse):
#* grid posterior over d given responses with scored abilities and a prior.
#* Body: {a, responses: [{theta, u}], prior: {mu_d, sd_d} or {mu_b, sd_b}}
#* se_b = se_d / a exactly (a fixed) — a valid difficulty-view SE.
#* @post /update-item
#* @serializer unboxedJSON list(digits = 15)
function(req) {
  body <- fromJSON(req$postBody)
  if (is.null(body$a) || body$a <= 0) return(list(error = "require a > 0"))
  update_item(as.numeric(body$a), as.data.frame(body$responses),
              as.list(body$prior))
}

#* Scale-linking diagnostics between two canonical parameter sets.
#* Body: {set_x: [{item, a, d}], set_y: [{item, a, d}]}
#* @post /link
#* @serializer unboxedJSON list(digits = 15)
function(req) {
  body <- fromJSON(req$postBody)
  link_stats(as.data.frame(body$set_x), as.data.frame(body$set_y))
}
