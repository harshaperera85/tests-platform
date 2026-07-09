# Build-time verification for the Analysis-seed endpoints (irt_core.R):
# fails the Docker image if joint calibration cannot recover known simulated
# parameters in canonical form, if the fixed-a update posterior misbehaves,
# or if link diagnostics break. Mirrors convert_difficulty_selftest.R's role.
source("/app/irt_core.R")
set.seed(20260709)

# ---- 1. joint calibration recovers simulated truth (canonical a, d) --------
J <- 30; N <- 1500
a_true <- runif(J, 0.7, 2.0)
d_true <- rnorm(J, 0, 1.2)
dat <- mirt::simdata(a = matrix(a_true), d = matrix(d_true), N = N,
                     itemtype = rep("2PL", J))
long <- do.call(rbind, lapply(seq_len(J), function(j)
  data.frame(person = seq_len(N), item = paste0("it", sprintf("%02d", j)),
             u = dat[, j])))
res <- fit_joint(long)
stopifnot(res$convergence$converged)
a_hat <- sapply(res$items, `[[`, "a"); d_hat <- sapply(res$items, `[[`, "d")
stopifnot(cor(a_hat, a_true) > 0.9, cor(d_hat, d_true) > 0.95)
stopifnot(all(sapply(res$items, function(x) x$var_a > 0 && x$var_d > 0)))
# vcov-alignment proof: coef()'s SEs must equal sqrt of the vcov diagonals we
# indexed per item — a row/item misalignment would break this, not just >0.
stopifnot(all(sapply(res$items, function(x)
  abs(x$se_a - sqrt(x$var_a)) < 1e-6 && abs(x$se_d - sqrt(x$var_d)) < 1e-6)))
stopifnot(res$metric$form == "slope-intercept", res$metric$scaling_d == 1)
cat("selftest 1 (joint recovery): a_r =", round(cor(a_hat, a_true), 3),
    "d_r =", round(cor(d_hat, d_true), 3), "OK\n")

# ---- 2. fixed-a update: posterior contracts toward truth, prior math -------
a <- 1.2; b_true <- 0.8; d_true1 <- -a * b_true
th <- rnorm(400)
u <- rbinom(400, 1, plogis(a * th + d_true1))
up <- update_item(a, data.frame(theta = th, u = u),
                  prior = list(mu_b = 0, sd_b = 1.0))
stopifnot(abs(up$b - b_true) < 0.25)             # recovers truth
stopifnot(up$se_b < 0.2)                          # precision from n=400
stopifnot(abs(up$se_b - up$se_d / a) < 1e-9)      # exact fixed-a SE map
few <- update_item(a, data.frame(theta = th[1:5], u = u[1:5]),
                   prior = list(mu_b = 0, sd_b = 0.3))
stopifnot(abs(few$b) < abs(up$b))                 # few responses -> prior pull
cat("selftest 2 (fixed-a update): b_hat =", round(up$b, 3),
    "se_b =", round(up$se_b, 3), "OK\n")

# ---- 2b. EAP scoring recovers a known ability -------------------------------
params <- data.frame(item = paste0("it", sprintf("%02d", 1:J)),
                     a = a_true, d = d_true)
th_true <- 1.1
ths <- replicate(25, {
  u_resp <- rbinom(J, 1, plogis(a_true * th_true + d_true))
  eap_score(params, data.frame(item = params$item, u = u_resp))$theta
})
# estimator property, not one draw: mean of 25 EAPs near truth (allowing the
# EAP prior shrinkage toward 0 expected at theta=1.1 with ~30 items)
stopifnot(abs(mean(ths) - th_true) < 0.25, sd(ths) < 0.6)
cat("selftest 2b (EAP, 25 persons): mean =", round(mean(ths), 3),
    "sd =", round(sd(ths), 3), "OK\n")

# ---- 3. link diagnostics ----------------------------------------------------
sx <- data.frame(item = paste0("it", 1:20), a = a_true[1:20], d = d_true[1:20])
sy <- transform(sx, d = d + 0.5 * a)              # b shifted by -0.5 exactly
lk <- link_stats(sx, sy)
stopifnot(lk$n_common == 20, abs(lk$mean_shift_b + 0.5) < 1e-9, lk$r_b > 0.999)
cat("selftest 3 (link): mean_shift_b =", round(lk$mean_shift_b, 3), "OK\n")
cat("ALL ANALYSIS-SEED SELFTESTS PASSED\n")
