# Canonical scoring / IRT service (mirt) — STUB for Phase 0.
#
# This is the single source of truth for the theta metric (CLAUDE.md golden rule
# 4). Phase 0 ships only a health endpoint so the stack stands up; the mirt-backed
# scoring endpoints (and the D=1.702 scaling handling) arrive with the metric
# layer. mirt is intentionally NOT installed yet to keep the image small/fast.

#* Liveness check
#* @get /health
#* @serializer unboxedJSON
function() {
  list(
    status = "ok",
    service = "scoring-r",
    role = "canonical-theta-metric",
    phase = "stub"
  )
}
