#!/usr/bin/env bash
# Continuous PR stewardship: while GitHub shows open PRs (or force flag), run one
# repo-factory cycle then sleep. Pair with pocket canon:
#   logline canon/v0.1/pocket/source/pr_stewardship.loop.v0.1.*
#
# Env:
#   PR_STEWARD_ROOT   — git repo to work in (default: directory containing repo-forge)
#   REPO_FORGE_HOME   — installation root of repo-forge (default: inferred from this script)
#   REPO_FORGE_BIN    — override path to repo-factory executable
#   PR_STEWARD_INTERVAL — seconds between iterations (default: 120)
#   PR_STEWARD_GOAL   — prompt passed to repo-factory each cycle
#   PR_STEWARD_FORCE  — if 1, run a cycle even when no open PRs
#   PR_STEWARD_CANON  — extra one-line canon reminder appended to default goal
#
set -euo pipefail

FORGE_HOME="$(cd "$(dirname "$0")/.." && pwd)"
WORKDIR="${PR_STEWARD_ROOT:-$FORGE_HOME}"
cd "$WORKDIR"

INTERVAL="${PR_STEWARD_INTERVAL:-120}"
FORCE="${PR_STEWARD_FORCE:-0}"

FACTORY="${REPO_FORGE_BIN:-$FORGE_HOME/repo-factory}"
if [[ ! -x "$FACTORY" ]]; then
  echo "repo-factory not executable at $FACTORY — set REPO_FORGE_BIN or install repo-forge." >&2
  exit 1
fi

CANON_HINT="${PR_STEWARD_CANON:-}"
if [[ -z "$CANON_HINT" ]]; then
  CANON_HINT="Respect pocket PR stewardship laws: pocket_gate, verify_gate, drift_gate (minilab pocket notes/pr_stewardship.md + pr_stewardship.loop.v0.1.json)."
fi

DEFAULT_GOAL="You are the authorized_steward. ${CANON_HINT}

One cycle: (1) List open PRs with gh; pick the highest-leverage item or the one the operator would merge next. (2) Review diff + CI requirements; run local checks that exist. (3) Fix or comment; push updates or open a focused PR. (4) Scan drift vs pocket canon JSON + slot runtime crates paths in pr_stewardship.loop canon; if drift, open realignment PR or document FAILED. (5) Final report only: DONE or FAILED, PR URLs, commands, tests, drift outcome.

Do not ask questions. If gh or permissions missing, FAILED with exact blocker."

GOAL="${PR_STEWARD_GOAL:-$DEFAULT_GOAL}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found; install GitHub CLI." >&2
  exit 1
fi

echo "pr_steward_loop workdir=$(pwd) forge=$(dirname "$FACTORY") interval=${INTERVAL}s force=${FORCE}"

while true; do
  OPEN=$(gh pr list --state open --json number --jq 'length' 2>/dev/null || echo 0)
  if [[ "$OPEN" =~ ^[0-9]+$ ]] && { [[ "$OPEN" -gt 0 ]] || [[ "$FORCE" == "1" ]]; }; then
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") cycle start (open_prs=$OPEN)"
    "$FACTORY" "$GOAL" || echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") cycle exit code $?"
  else
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") dormant (open_prs=$OPEN), sleeping ${INTERVAL}s"
  fi
  sleep "$INTERVAL"
done
