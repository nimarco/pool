#!/usr/bin/env bash
# Identity and safety check. Run before anything that can create AWS resources or spend.
# Refuses to proceed on root credentials (AGENTS.md §3.5).
#
# Resolves identity through the AWS CLI when it is available, and otherwise through the
# project's own boto3 — the repository always has boto3, and "which principal am I?" is
# too important a question to fail on a missing binary.
set -euo pipefail
cd "$(dirname "$0")/.."

AGENT_PY="services/agent/.venv/bin/python"

echo "→ Checking AWS identity…"
IDENTITY=""
if command -v aws >/dev/null 2>&1; then
  IDENTITY=$(aws sts get-caller-identity --output json 2>/dev/null || true)
fi

if [[ -z "$IDENTITY" && -x "$AGENT_PY" ]]; then
  IDENTITY=$("$AGENT_PY" - <<'PY' 2>/dev/null || true
import json, os, boto3
profile = os.environ.get("AWS_PROFILE") or None
region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or None
session = boto3.Session(profile_name=profile, region_name=region)
identity = session.client("sts").get_caller_identity()
print(json.dumps({
    "Arn": identity["Arn"],
    "Account": identity["Account"],
    "Region": session.region_name or "unset",
}))
PY
)
fi

if [[ -z "$IDENTITY" ]]; then
  echo "✗ No usable AWS credentials." >&2
  echo "  Configure a profile or role first. Never paste long-lived access keys into" >&2
  echo "  this repository. If the profile uses the AWS CLI login flow, the local venv" >&2
  echo "  also needs: uv pip install --python $AGENT_PY 'botocore[crt]'" >&2
  exit 1
fi

read -r ARN ACCOUNT IDENTITY_REGION <<<"$(
  printf '%s' "$IDENTITY" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d["Arn"], d["Account"], d.get("Region", "unset"))
'
)"

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ -z "$REGION" ]]; then
  if command -v aws >/dev/null 2>&1; then
    REGION=$(aws configure get region 2>/dev/null || true)
  fi
  REGION="${REGION:-$IDENTITY_REGION}"
fi

echo "  account : $ACCOUNT"
echo "  region  : $REGION"
echo "  arn     : $ARN"

# Root looks like arn:aws:iam::123456789012:root
if [[ "$ARN" == *":root" ]]; then
  echo "✗ These are ROOT account credentials. Refusing to proceed." >&2
  echo "  Create an IAM user or role with least privilege and use that instead." >&2
  exit 1
fi

if [[ -z "$REGION" || "$REGION" == "unset" || "$REGION" == "None" ]]; then
  echo "✗ No region configured. Set AWS_REGION." >&2
  exit 1
fi

echo "✓ Identity looks safe to proceed with."
