#!/usr/bin/env bash
# Look for anything credential-shaped before the repo goes public.
set -uo pipefail
cd "$(dirname "$0")/.."

# cdk.out* are CDK synth output. The demo stack's synth copies the whole Lambda
# bundle in as an asset directory, so excluding it here is the same decision as
# excluding cdk.out itself — generated, never committed, and full of other people's
# vendored wheels.
EXCLUDES=(--exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv
          --exclude-dir=dist --exclude-dir=cdk.out --exclude-dir=cdk.out.test
          --exclude-dir=cdk.out.demo --exclude-dir=cdk.out.demotest
          --exclude-dir=__pycache__ --exclude-dir=.pytest_cache
          --exclude=secret_scan.sh --exclude=secret_scan_selftest.sh
          --exclude=package-lock.json)

# The AgentCore CLI's CodeZip staging tree: ~120 MB of vendored third-party wheels,
# rebuilt by every `agentcore deploy` synth and never committed. Scanning it only ever
# reports other people's documentation fixtures — botocore's AKIA…EXAMPLE keys, the PEM
# header constant in `cryptography` — never ours.
#
# Pruned by exact rooted path, not by directory name. `--exclude-dir` deliberately is
# not used for this: it matches a basename, so `--exclude-dir=.cache` would blind the
# scanner to every `.cache` directory anywhere in the repository. Filtering afterwards
# costs about half a second on the whole tree and keeps the exemption to this one path.
#
# `build/demo-lambda/` is the same situation for the same reason: the public-demo
# Lambda bundle, ~70 MB of vendored wheels rebuilt by `make demo-bundle` and never
# committed. `scripts/build_demo_bundle.sh` runs these patterns over the parts of that
# bundle this project actually wrote, which is the check that has any signal in it.
GENERATED_CACHE='^\./(agentcore/\.cache|build/demo-lambda)/'

FAIL=0
scan() {
  local label="$1" pattern="$2"
  local hits
  hits=$(grep -rInE "${EXCLUDES[@]}" "$pattern" . 2>/dev/null | grep -vE "$GENERATED_CACHE" || true)
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

# Payment credentials. A live key is a hard failure; a *test* key still must not be
# committed, because a committed secret is a committed secret whatever it unlocks.
# The prefixes below are matched with a following key body so the bare strings in
# documentation and in the provider's own refusal check do not trip the scan.
scan "Stripe live secret key"    'sk_live_[A-Za-z0-9]{16,}'
scan "Stripe restricted key"     'rk_live_[A-Za-z0-9]{16,}'
scan "Stripe test secret key"    'sk_test_[A-Za-z0-9]{16,}'
scan "Stripe webhook secret"     'whsec_[A-Za-z0-9]{20,}'

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
