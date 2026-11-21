#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export API_PORT="${API_PORT:-8000}"
export PORT="${PORT:-3000}"
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
.venv/bin/uvicorn main:app --host 0.0.0.0 --port "$API_PORT" &
pids+=("$!")
cd "$APP_DIR/web"
./node_modules/.bin/next start --hostname 0.0.0.0 --port "$PORT" &
pids+=("$!")
wait -n "${pids[@]}"
