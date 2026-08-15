#!/usr/bin/env bash
# Verify a deployed API actually works. Read-only plus one bounded agent run.
set -euo pipefail
API_URL="${API_URL:-}"
if [[ -z "$API_URL" ]]; then
  echo "usage: API_URL=https://xxxx.execute-api.us-east-1.amazonaws.com make smoke" >&2
  exit 1
fi
WS="smoke$(date +%s)"
echo "→ health"
curl -fsS "$API_URL/api/health" | python3 -m json.tool | head -12
echo "→ seeding workspace $WS"
curl -fsS -X POST "$API_URL/api/demo/reset?workspace=$WS" | python3 -m json.tool
echo "→ one bounded coordination run"
curl -fsS -X POST "$API_URL/api/agent/run?workspace=$WS" \
  -H 'content-type: application/json' -d '{"trigger":"smoke_test"}' | python3 -m json.tool
echo "→ resulting state"
curl -fsS "$API_URL/api/state?workspace=$WS" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"pools={len(d[\"pools\"])} decisions={len(d[\"decisions\"])} savings={d[\"metrics\"][\"collective_savings_cents\"]}c")'
echo "✓ smoke test passed (workspace $WS expires via TTL)"
