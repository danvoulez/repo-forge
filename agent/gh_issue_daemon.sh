#!/usr/bin/env bash
# Poll GitHub Issues (e.g. opened from the GitHub iPhone app), run repo-forge locally,
# comment with the report, close the issue.
#
# One-time:
#   gh label create repo-forge --repo OWNER/REPO --description "repo-forge queue"
# Use a private repo or GH_FORGE_ISSUE_ALLOWED_AUTHORS — anyone who can open issues
# can trigger code execution on your Mac if they guess the label.
#
# Env:
#   GH_FORGE_ISSUE_REPO        — required, owner/name (e.g. danvoulez/repo-forge)
#   GH_FORGE_ISSUE_LABEL       — default repo-forge
#   GH_FORGE_ISSUE_POLL_INTERVAL — seconds (default 45)
#   GH_FORGE_ISSUE_ALLOWED_AUTHORS — optional comma-separated logins (e.g. danvoulez,bot)
#   REPO_FACTORY_CWD           — working copy for the agent (default: this repo root)
#
set -euo pipefail

FORGE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$FORGE_ROOT"

REPO="${GH_FORGE_ISSUE_REPO:?Set GH_FORGE_ISSUE_REPO to owner/name}"
LABEL="${GH_FORGE_ISSUE_LABEL:-repo-forge}"

INTERVAL_RAW="${GH_FORGE_ISSUE_POLL_INTERVAL:-45}"
if [[ ! "$INTERVAL_RAW" =~ ^[0-9]+$ ]] || [[ "$INTERVAL_RAW" -lt 5 ]]; then
  echo "GH_FORGE_ISSUE_POLL_INTERVAL must be integer >= 5; got: $INTERVAL_RAW" >&2
  exit 1
fi

WORKDIR="${REPO_FACTORY_CWD:-$FORGE_ROOT}"
export REPO_FACTORY_CWD="$WORKDIR"

_POLL_TRUNCATE_PY="$FORGE_ROOT/agent/_truncate_comment.py"
if [[ ! -f "$_POLL_TRUNCATE_PY" ]]; then
  echo "missing $_POLL_TRUNCATE_PY" >&2
  exit 1
fi

# Normalise allowlist as comma-surrounded for substring match
ALLOW_NORM=",${GH_FORGE_ISSUE_ALLOWED_AUTHORS:-},"
_login_ok() {
  local login="$1"
  [[ -z "${GH_FORGE_ISSUE_ALLOWED_AUTHORS:-}" ]] && return 0
  [[ "$ALLOW_NORM" == *",$login,"* ]]
}

truncate_comment() {
  python3 "$_POLL_TRUNCATE_PY" "$1" "$2"
}

echo "gh_issue_daemon repo=$REPO label=$LABEL cwd=$WORKDIR interval=${INTERVAL_RAW}s"

while true; do
  nums="$(gh issue list --repo "$REPO" --label "$LABEL" --state open --json number --jq '.[].number' 2>/dev/null || true)"
  for num in $nums; do
    [[ -z "$num" ]] && continue
    author="$(gh issue view "$num" --repo "$REPO" --json author --jq '.author.login' 2>/dev/null || echo "")"
    if ! _login_ok "$author"; then
      echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") skip #$num author=$author (not in allowlist)"
      gh issue comment "$num" --repo "$REPO" --body "repo-forge: ignored (author \`$author\` not in GH_FORGE_ISSUE_ALLOWED_AUTHORS)." || true
      gh issue close "$num" --repo "$REPO" || true
      continue
    fi

    body="$(gh issue view "$num" --repo "$REPO" --json body --jq '.body' 2>/dev/null || echo "")"
    if [[ -z "${body//[$'\t\r\n ']}" ]]; then
      gh issue comment "$num" --repo "$REPO" --body "repo-forge: empty issue body; closing." || true
      gh issue close "$num" --repo "$REPO" || true
      continue
    fi

    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") run #$num by $author"
    report="$FORGE_ROOT/outbox/gh-${num}.report.txt"
    comment_file="$FORGE_ROOT/outbox/gh-${num}.comment.txt"
    set +e
    "$FORGE_ROOT/repo-factory" "$body" >"$report" 2>&1
    ec=$?
    set -e
    {
      echo ""
      echo "--- repo-factory exit code: $ec ---"
    } >>"$report"

    truncate_comment "$report" "$comment_file"

    gh issue comment "$num" --repo "$REPO" --body-file "$comment_file" || true
    gh issue close "$num" --repo "$REPO" || true
  done
  sleep "$INTERVAL_RAW"
done
