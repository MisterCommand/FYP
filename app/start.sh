#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pids=()
cleanup() {
  trap - EXIT INT TERM
  if ((${#pids[@]})); then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM
cd "$APP_DIR/api"
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 &
pids+=("$!")
cd "$APP_DIR/web"
./node_modules/.bin/next start --hostname 0.0.0.0 --port "${PORT:-3000}" &
pids+=("$!")
wait -n "${pids[@]}"
