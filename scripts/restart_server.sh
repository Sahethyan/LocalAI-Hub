#!/usr/bin/env bash
# Restart LocalAI Hub (default port 8081). Run from project root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-8081}"
HOST="${HOST:-0.0.0.0}"

echo "Stopping anything on port ${PORT}..."
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
fi
# Fallback: kill uvicorn bound to this port
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -t -i ":${PORT}" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "${PIDS}" ]]; then
    kill -9 ${PIDS} 2>/dev/null || true
  fi
fi
sleep 1

if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
  echo ""
  echo "Port ${PORT} is still in use."
  echo "  1. Find the Cursor/terminal tab running uvicorn on ${PORT}"
  echo "  2. Press Ctrl+C in that terminal"
  echo "  3. Run this script again: ./scripts/restart_server.sh"
  echo ""
  echo "Or from your shell: fuser -k ${PORT}/tcp"
  exit 1
fi

if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
# shellcheck source=/dev/null
source venv/bin/activate

echo "Starting LocalAI Hub on http://${HOST}:${PORT} (with --reload)..."
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
