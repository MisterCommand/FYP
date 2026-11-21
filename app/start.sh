#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export API_PORT="${API_PORT:-8000}"
export PORT="${PORT:-3000}"
export API_HOST="${API_HOST:-127.0.0.1}"
export WEB_HOST="${WEB_HOST:-127.0.0.1}"
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
.venv/bin/python security.py
.venv/bin/uvicorn main:app --host "$API_HOST" --port "$API_PORT" --no-proxy-headers &
pids+=("$!")
cd "$APP_DIR/web"
./node_modules/.bin/next start --hostname "$WEB_HOST" --port "$PORT" &
pids+=("$!")
wait -n "${pids[@]}"
