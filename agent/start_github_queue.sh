#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${REPO_FORGE_ENV:-$ROOT/agent/github-queue.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export GH_FORGE_ISSUE_REPO="${GH_FORGE_ISSUE_REPO:?Set GH_FORGE_ISSUE_REPO in $ENV_FILE or env}"
export GH_FORGE_ISSUE_ALLOWED_AUTHORS="${GH_FORGE_ISSUE_ALLOWED_AUTHORS:-}"

if [[ "${SKIP_REPO_FORGE_DOCTOR:-0}" != "1" ]]; then
  "$ROOT/agent/doctor.sh"
fi

exec "$ROOT/agent/gh_issue_daemon.sh"
