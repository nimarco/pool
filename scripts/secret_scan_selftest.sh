#!/usr/bin/env bash
# Prove that secret_scan.sh still finds real secrets.
#
# A scanner that cannot fail is worse than no scanner: it reports "clean" forever and
# everyone believes it. `secret_scan.sh` prunes exactly one path — the AgentCore CLI's
# generated staging cache — and this asserts that the prune is that narrow: a planted
# secret is caught everywhere else, including in a `.cache` directory somewhere else in
# the repository, and only the AgentCore path is exempt.
#
# Plants fake credentials under a temporary directory, runs the real scanner, and always
# cleans up. Costs nothing and touches no AWS or Stripe.
set -uo pipefail
cd "$(dirname "$0")/.."

PLANT_ROOT=".secret_scan_selftest"
CACHE_PLANT="agentcore/.cache/__selftest__"
FAIL=0

cleanup() { rm -rf "$PLANT_ROOT" "$CACHE_PLANT"; }
trap cleanup EXIT INT TERM
cleanup

# Assembled at runtime so the literals never sit in this file — the scanner reads it too.
AWS_KEY="AKIA""IOSFODNN7EXAMPLE"
STRIPE_LIVE="sk_""live_""51H8xKfakefakefakefake"
STRIPE_TEST="sk_""test_""51H8xKfakefakefakefake"
WEBHOOK="whsec_""fakefakefakefakefakefakefake"

expect() {
  local want="$1" where="$2"
  if bash scripts/secret_scan.sh >/dev/null 2>&1; then got="clean"; else got="detected"; fi
  if [[ "$got" == "$want" ]]; then
    printf '  ✓ %-52s %s\n' "$where" "$got"
  else
    printf '  ✗ %-52s expected %s, got %s\n' "$where" "$want" "$got"
    FAIL=1
  fi
}

echo "→ Baseline"
expect clean "no planted secret"

echo "→ Genuine secrets must be detected outside the generated cache"
for spec in \
  "$PLANT_ROOT/config.py:$AWS_KEY" \
  "$PLANT_ROOT/nested/deep/payments.py:$STRIPE_LIVE" \
  "$PLANT_ROOT/nested/deep/test_fixture.py:$STRIPE_TEST" \
  "$PLANT_ROOT/hooks.py:$WEBHOOK" \
  "$PLANT_ROOT/.cache/leaked.py:$AWS_KEY" \
  "services/agent/.cache/leaked.py:$AWS_KEY" \
  "agentcore/leaked.py:$AWS_KEY"
do
  path="${spec%%:*}"; value="${spec#*:}"
  mkdir -p "$(dirname "$path")"
  printf 'KEY = "%s"\n' "$value" > "$path"
  expect detected "$path"
  rm -rf "$path"
done
# The two directories above may have been created by this test; drop them if now empty.
rmdir services/agent/.cache 2>/dev/null || true

echo "→ Only the AgentCore CLI's generated staging cache is exempt"
mkdir -p "$CACHE_PLANT"
printf 'KEY = "%s"\n' "$AWS_KEY" > "$CACHE_PLANT/vendored_fixture.py"
expect clean "agentcore/.cache/ (generated, never committed)"
rm -rf "$CACHE_PLANT"

echo "→ Cleaned up"
expect clean "after cleanup"

if [[ $FAIL -eq 0 ]]; then
  echo "✓ secret scan self-test passed"
else
  echo
  echo "Secret scan self-test FAILED — the scanner's coverage is not what it claims."
  exit 1
fi
