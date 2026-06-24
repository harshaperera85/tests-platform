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
#* @serializer unboxedJSON
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
#* @serializer unboxedJSON
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
