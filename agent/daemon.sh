#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export REPO_FACTORY_CWD="${REPO_FACTORY_CWD:-$ROOT}"

while true; do
  shopt -s nullglob
  for task in inbox/*.txt; do
    name="$(basename "$task" .txt)"
    echo "Running $name"
    set +e
    ./repo-factory "$(cat "$task")" > "outbox/${name}.report.txt" 2>&1
    ec=$?
    set -e
    {
      echo ""
      echo "--- exit code: $ec ---"
    } >> "outbox/${name}.report.txt"
    mv "$task" "outbox/${name}.done.txt"
  done
  sleep 10
done
