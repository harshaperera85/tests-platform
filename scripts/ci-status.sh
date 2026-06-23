#!/usr/bin/env bash
# ci-status.sh — report GitHub Actions status for a commit (READ-ONLY).
#
# Reads the auth token from the GH_TOKEN environment variable ONLY. It never
# prints, stores, hardcodes, or commits the token value. Use after a push to
# confirm the workflow run(s) for a commit went green (CLAUDE.md golden rule 9).
#
# Usage:
#   GH_TOKEN=<read-only-token> scripts/ci-status.sh [SHA] [--wait] [--timeout=SECONDS]
#     SHA            commit to check (default: current HEAD)
#     --wait         poll until all runs for the commit complete (or timeout)
#     --timeout=N    max seconds to wait with --wait (default: 600)
#
# Transport: uses the gh CLI if installed (gh reads GH_TOKEN automatically),
# otherwise the GitHub REST API via curl. Exit code: 0 only if every workflow
# run for the commit completed with conclusion=success.
set -euo pipefail

SHA=""
WAIT=0
TIMEOUT=600
for a in "$@"; do
  case "$a" in
    --wait) WAIT=1 ;;
    --timeout=*) TIMEOUT="${a#*=}" ;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown option: $a" >&2; exit 2 ;;
    *) SHA="$a" ;;
  esac
done

if [ -z "${GH_TOKEN:-}" ]; then
  echo "error: GH_TOKEN is not set. Export a read-only token in your shell first," >&2
  echo "       e.g.  export GH_TOKEN=<token>   (never commit or print the value)." >&2
  exit 2
fi
export GH_TOKEN  # ensure child gh/curl inherit it

# Resolve to a full 40-char SHA — the Actions API head_sha filter doesn't match
# abbreviated SHAs.
SHA="$(git rev-parse --verify "${SHA:-HEAD}^{commit}" 2>/dev/null || echo "${SHA}")"
REPO="$(git remote get-url origin \
  | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"

# Fetch a REST path -> JSON on stdout. Prefer gh; fall back to curl.
api() {
  if command -v gh >/dev/null 2>&1; then
    gh api "$1"
  else
    curl -sS -H "Authorization: Bearer ${GH_TOKEN}" \
         -H "Accept: application/vnd.github+json" \
         "https://api.github.com/$1"
  fi
}

runs_for_sha() { api "repos/${REPO}/actions/runs?head_sha=${SHA}&per_page=20"; }

started=$SECONDS
runs_json="$(runs_for_sha)"
if [ "$WAIT" = "1" ]; then
  while :; do
    pending="$(printf '%s' "$runs_json" | python3 -c \
      'import json,sys; r=json.load(sys.stdin)["workflow_runs"]; print(sum(1 for x in r if x["status"]!="completed"))')"
    total="$(printf '%s' "$runs_json" | python3 -c \
      'import json,sys; print(len(json.load(sys.stdin)["workflow_runs"]))')"
    if [ "$total" -gt 0 ] && [ "$pending" -eq 0 ]; then break; fi
    if [ $((SECONDS - started)) -ge "$TIMEOUT" ]; then
      echo "… timed out after ${TIMEOUT}s waiting for runs to complete" >&2
      break
    fi
    echo "… ${pending}/${total} run(s) in progress; waiting 15s"
    sleep 15
    runs_json="$(runs_for_sha)"
  done
fi

echo "CI status for ${REPO} @ ${SHA:0:7}"
printf '%s' "$runs_json" | python3 -c '
import json, sys
runs = json.load(sys.stdin)["workflow_runs"]
if not runs:
    print("  (no workflow runs found for this commit yet)")
for r in runs:
    print("  - %s: %s -> %s  (run %s)" % (r["name"], r["status"], r.get("conclusion"), r["id"]))
'

# Per-job breakdown for each run.
ids="$(printf '%s' "$runs_json" | python3 -c \
  'import json,sys; [print(x["id"]) for x in json.load(sys.stdin)["workflow_runs"]]')"
for id in $ids; do
  api "repos/${REPO}/actions/runs/${id}/jobs" | python3 -c '
import json, sys
for j in json.load(sys.stdin)["jobs"]:
    print("      - %s: %s -> %s" % (j["name"], j["status"], j.get("conclusion")))
'
done

verdict="$(printf '%s' "$runs_json" | python3 -c '
import json, sys
runs = json.load(sys.stdin)["workflow_runs"]
if not runs:
    print("NONE")
elif any(r["status"] != "completed" for r in runs):
    print("PENDING")
else:
    print("PASS" if all(r.get("conclusion") == "success" for r in runs) else "FAIL")
')"

echo "verdict: ${verdict}"
[ "$verdict" = "PASS" ] && exit 0 || exit 1
