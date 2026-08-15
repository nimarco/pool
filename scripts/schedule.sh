#!/usr/bin/env bash
# Enable or disable the background scan. Enabling starts recurring model invocations.
set -euo pipefail
ACTION="${1:-}"
STACK="${POOL_STACK_NAME:-PoolStack}"

RULE=$(aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='ScanRuleName'].OutputValue" --output text 2>/dev/null || true)

if [[ -z "$RULE" || "$RULE" == "None" ]]; then
  echo "✗ Could not find the scan rule. Is $STACK deployed?" >&2
  exit 1
fi

case "$ACTION" in
  enable)
    echo "⚠️  Enabling '$RULE' starts a recurring job that invokes the model every 6 hours."
    read -r -p "Type ENABLE to confirm: " confirm
    [[ "$confirm" == "ENABLE" ]] || { echo "aborted"; exit 1; }
    aws events enable-rule --name "$RULE"
    echo "✓ enabled. Disable again with: make schedule-off"
    ;;
  disable)
    aws events disable-rule --name "$RULE"
    echo "✓ '$RULE' disabled — no further scheduled runs."
    ;;
  *)
    echo "usage: $0 {enable|disable}" >&2; exit 1 ;;
esac
