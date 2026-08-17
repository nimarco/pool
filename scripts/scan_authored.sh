#!/usr/bin/env bash
# Scan directories of *Pool's own* code for credential-shaped strings.
#
# Separate from scripts/secret_scan.sh, which scans the repository. This one is
# pointed at build output — the public-demo Lambda bundle — where the vast majority of
# files are third-party wheels that legitimately contain documentation keys
# (botocore's AKIA…EXAMPLE) and CA bundles. Scanning those produces findings nobody
# can act on, and a check that always fires is a check everyone learns to skip.
#
# Usage: scripts/scan_authored.sh DIR [DIR...]
set -uo pipefail

if [[ $# -eq 0 ]]; then
  echo "usage: $0 DIR [DIR...]" >&2
  exit 2
fi

HITS=$(grep -rInE \
  -e '(AKIA|ASIA)[A-Z0-9]{16}' \
  -e 'aws_secret_access_key[[:space:]]*=' \
  -e 'aws_session_token[[:space:]]*=' \
  -e 'BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY' \
  -e '(sk_live_|rk_live_|sk_test_|whsec_)[A-Za-z0-9]{16,}' \
  "$@" 2>/dev/null || true)

if [[ -n "$HITS" ]]; then
  echo "✗ credential-shaped string in code that would be shipped:" >&2
  echo "$HITS" | head -8 >&2
  exit 1
fi
exit 0
