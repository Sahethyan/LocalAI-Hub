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
  STUCK_PID=""
  if command -v lsof >/dev/null 2>&1; then
    STUCK_PID=$(lsof -t -i ":${PORT}" -sTCP:LISTEN 2>/dev/null | head -1)
  fi
  echo ""
  echo "Port ${PORT} is still in use${STUCK_PID:+ (PID ${STUCK_PID})}."
  echo ""
  echo "If fuser/kill say 'Permission denied', the old server was started by Cursor"
  echo "and is stuck in cursor_sandbox. Use one of these:"
  echo ""
  echo "  sudo kill -9 ${STUCK_PID:-<PID>}    # enter your password"
  echo "  # or: quit and restart Cursor IDE, then run this script again"
  echo ""
  exit 1
fi

if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
# shellcheck source=/dev/null
source venv/bin/activate

echo "Starting LocalAI Hub on http://${HOST}:${PORT} (with --reload)..."
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
