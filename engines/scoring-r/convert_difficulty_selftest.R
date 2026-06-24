# Build-time parity tripwire for /convert-difficulty.
#
# The endpoint's PRODUCTION path is mirt::DeltaMethod (authoritative). This selftest
# asserts that, on a genuinely fitted model, three independent computations of SE(b)
# agree and none is a copy of SE(d):
#   1. mirt::DeltaMethod(fn, c(a,d), acov)      <- the endpoint's production call
#   2. coef(mod, IRTpars=TRUE, printSE=TRUE)    <- mirt's reparameterization SEs
#   3. analytic Jacobian  Var(b)=J Σ Jᵀ         <- independent closed form
# Fails the image build (non-zero exit) on any divergence.
suppressMessages(library(mirt))

fn <- function(p) -p[2] / p[1]                              # b = -d/a
analytic_se_b <- function(a, d, Va, Vd, Cad) {
  J1 <- d / (a * a); J2 <- -1 / a
  sqrt(J1 * J1 * Va + J2 * J2 * Vd + 2 * J1 * J2 * Cad)
}

set.seed(7)
a_true <- matrix(c(1.3, 0.8, 1.6, 1.0, 1.2))
d_true <- matrix(c(-0.5, 0.9, 0.2, -1.1, 0.4))
dat <- simdata(a = a_true, d = d_true, N = 4000, itemtype = "2PL")
mod <- mirt(dat, 1, itemtype = "2PL", verbose = FALSE, SE = TRUE)

V <- vcov(mod)
ok <- TRUE
for (i in seq_len(5)) {
  si <- coef(mod, printSE = TRUE)[[i]]
  tr <- coef(mod, IRTpars = TRUE, printSE = TRUE)[[i]]
  a1 <- si["par", "a1"]; d1 <- si["par", "d"]
  an <- sprintf("a1.%d", 4 * i - 3); dn <- sprintf("d.%d", 4 * i - 2)
  acov <- matrix(c(V[an, an], V[an, dn], V[an, dn], V[dn, dn]), 2, 2)

  se_delta_mirt <- as.numeric(DeltaMethod(fn, c(a1, d1), acov)$se)  # production path
  se_coef <- tr["SE", "b"]                                          # mirt IRTpars
  se_analytic <- analytic_se_b(a1, d1, V[an, an], V[dn, dn], V[an, dn])
  se_d <- si["SE", "d"]
  cat(sprintf("item %d: DeltaMethod=%.6f  coef(IRTpars)=%.6f  analytic=%.6f  SE(d)=%.6f\n",
              i, se_delta_mirt, se_coef, se_analytic, se_d))
  if (abs(se_delta_mirt - se_coef) > 1e-4) ok <- FALSE
  if (abs(se_delta_mirt - se_analytic) > 1e-4) ok <- FALSE
  if (abs(se_delta_mirt - se_d) < 1e-6) ok <- FALSE  # must NOT equal SE(d)
}
if (!ok) { cat("SELFTEST FAILED\n"); quit(status = 1) }
cat("SELFTEST OK: DeltaMethod == coef(IRTpars) == analytic, all != SE(d)\n")
