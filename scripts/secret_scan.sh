#!/usr/bin/env bash
# Look for anything credential-shaped before the repo goes public.
set -uo pipefail
cd "$(dirname "$0")/.."

EXCLUDES=(--exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv
          --exclude-dir=dist --exclude-dir=cdk.out --exclude-dir=cdk.out.test
          --exclude-dir=__pycache__ --exclude-dir=.pytest_cache
          --exclude=secret_scan.sh --exclude=package-lock.json)

FAIL=0
scan() {
  local label="$1" pattern="$2"
  local hits
  hits=$(grep -rInE "${EXCLUDES[@]}" "$pattern" . 2>/dev/null || true)
  if [[ -n "$hits" ]]; then
    echo "✗ $label"
    echo "$hits" | head -8
    FAIL=1
  fi
}

# AKIA/ASIA access key ids, secret-key assignments, private keys, bearer tokens.
scan "AWS access key id"      '(AKIA|ASIA)[A-Z0-9]{16}'
scan "AWS secret access key"  'aws_secret_access_key[[:space:]]*=[[:space:]]*[A-Za-z0-9/+=]{30,}'
scan "private key block"      'BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY'
scan "hardcoded bearer token" 'Bearer[[:space:]]+[A-Za-z0-9._-]{30,}'
scan "generic api key assign" '(api[_-]?key|apikey|secret)[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9_\-]{24,}["'"'"']'

# A committed .env is a finding regardless of contents.
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "✗ .env is tracked by git"
  FAIL=1
fi

if [[ $FAIL -eq 0 ]]; then
  echo "✓ secret scan clean"
else
  echo
  echo "Secret scan FAILED. Remove the finding, then rotate anything that was exposed."
  exit 1
fi
