#!/usr/bin/env bash
# Identity and safety check. Run before anything that can create AWS resources.
# Refuses to proceed on root credentials (AGENTS.md §3.5, brief §12).
set -euo pipefail

if ! command -v aws >/dev/null 2>&1; then
  echo "✗ AWS CLI not found. Install it, then run 'aws configure'." >&2
  exit 1
fi

echo "→ Checking AWS identity…"
if ! IDENTITY=$(aws sts get-caller-identity --output json 2>/dev/null); then
  echo "✗ No usable AWS credentials. Configure a profile or role first." >&2
  echo "  Never paste long-lived access keys into this repository." >&2
  exit 1
fi

ARN=$(echo "$IDENTITY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Arn"])')
ACCOUNT=$(echo "$IDENTITY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])')
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || echo unset)}}"

echo "  account : $ACCOUNT"
echo "  region  : $REGION"
echo "  arn     : $ARN"

# Root looks like arn:aws:iam::123456789012:root
if [[ "$ARN" == *":root" ]]; then
  echo "✗ These are ROOT account credentials. Refusing to deploy." >&2
  echo "  Create an IAM user or role with least privilege and use that instead." >&2
  exit 1
fi

if [[ "$REGION" == "unset" ]]; then
  echo "✗ No region configured. Set AWS_REGION." >&2
  exit 1
fi

echo "✓ Identity looks safe to deploy with."
