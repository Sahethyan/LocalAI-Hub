#!/usr/bin/env bash
# Phase 4 deliverable: curl-based SSE stream test (requires Ollama on LAN).
set -euo pipefail

BASE="${BASE_URL:-http://127.0.0.1:8080}"
MODEL="${MODEL:-llama3.2:1b}"

echo "Creating chat with model=${MODEL}..."
CHAT_JSON=$(curl -sf -X POST "${BASE}/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"${MODEL}\"}")
CHAT_ID=$(echo "$CHAT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Chat id: ${CHAT_ID}"

echo "Streaming reply (SSE)..."
curl -sN -X POST "${BASE}/api/v1/chats/${CHAT_ID}/messages?stream=true" \
  -H "Content-Type: application/json" \
  -d '{"content": "Reply with exactly three words."}'

echo ""
