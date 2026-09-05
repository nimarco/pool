#!/usr/bin/env bash
# Verify a deployed API actually works. Read-only plus one bounded agent run.
set -euo pipefail
API_URL="${API_URL:-}"
if [[ -z "$API_URL" ]]; then
  echo "usage: API_URL=https://xxxx.execute-api.us-east-1.amazonaws.com make smoke" >&2
  exit 1
fi
# Shaped like a browser-generated session id — `w` then hex — because the public demo
# refuses anything else (`public_demo.PUBLIC_WORKSPACE_RE`), and the private stack's own
# rule is a superset of it. `smoke<timestamp>` failed the public one on every deploy.
WS="w$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
echo "→ health"
curl -fsS "$API_URL/api/health" | python3 -m json.tool | head -12
echo "→ seeding workspace $WS"
curl -fsS -X POST "$API_URL/api/demo/reset?workspace=$WS" | python3 -m json.tool
echo "→ one bounded coordination run"
# `manual_scan`, not an invented trigger: the public demo runs only the three actions in
# its own allowlist, and inventing a fourth is exactly what that allowlist is for.
curl -fsS -X POST "$API_URL/api/agent/run?workspace=$WS" \
  -H 'content-type: application/json' -d '{"trigger":"manual_scan"}' | python3 -m json.tool
echo "→ resulting state"
curl -fsS "$API_URL/api/state?workspace=$WS" \
  | python3 -c 'import json,sys
d = json.load(sys.stdin)
print("pools=%d decisions=%d savings=%dc" % (
    len(d["pools"]), len(d["decisions"]), d["metrics"]["collective_savings_cents"]))'
echo "✓ smoke test passed (workspace $WS expires via TTL)"
