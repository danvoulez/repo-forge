#!/usr/bin/env bash
# Preflight before repo-forge / GitHub queue daemons.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ERR=0

fail() {
  echo "doctor: $*" >&2
  ERR=1
}

[[ -d "$ROOT/.venv" ]] || fail "missing .venv — python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
[[ -x "$ROOT/repo-factory" ]] || fail "repo-factory not executable (chmod +x repo-factory)"
[[ -n "${ANTHROPIC_API_KEY:-}" ]] || fail "export ANTHROPIC_API_KEY (Anthropic API)"
command -v claude >/dev/null 2>&1 || fail "Claude Code CLI not on PATH (install @anthropic-ai/claude-code; expected: claude)"

if [[ "${CHECK_GH:-1}" == "1" ]]; then
  command -v gh >/dev/null 2>&1 || fail "GitHub CLI gh not on PATH"
  gh auth status >/dev/null 2>&1 || fail "run: gh auth login"
fi

if [[ "$ERR" -ne 0 ]]; then
  echo "doctor: fix above and retry (or SKIP_REPO_FORGE_DOCTOR=1 to bypass)." >&2
  exit 1
fi

echo "doctor: OK (venv, repo-forge, ANTHROPIC_API_KEY, claude$( [[ "${CHECK_GH:-1}" == "1" ]] && echo ', gh' ))."
exit 0
