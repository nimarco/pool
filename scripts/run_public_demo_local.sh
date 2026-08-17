#!/usr/bin/env bash
# Run the public judge demo locally, in exactly the configuration it deploys in.
#
# Same process shape as the Lambda: judge mode on, the built SPA served from the same
# origin as the API, simulated payments, simulated purchase, offline planner. The two
# deliberate differences are the in-memory store (no DynamoDB table locally) and the
# live AgentCore action, which stays OFF unless AGENTCORE_RUNTIME_ARN is exported —
# invoking it spends Bedrock tokens, so it is never on by accident.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f apps/web/dist/index.html ]]; then
  echo "→ Building the web app"
  npm run build --prefix apps/web >/dev/null
fi

export POOL_PUBLIC_DEMO=true
export PUBLIC_DEMO_WEB_ROOT="$PWD/apps/web/dist"
export PAYMENT_PROVIDER="${PAYMENT_PROVIDER:-simulated}"
export PURCHASE_EXECUTOR="${PURCHASE_EXECUTOR:-simulated}"
export MODEL_PROVIDER="${MODEL_PROVIDER:-offline}"

echo "→ http://127.0.0.1:${PORT:-8000}"
echo "  judge mode · in-memory store · live agent: ${AGENTCORE_RUNTIME_ARN:-off}"
exec services/agent/.venv/bin/python -m uvicorn pool.api.app:app \
  --app-dir services/agent --port "${PORT:-8000}" --host 127.0.0.1
