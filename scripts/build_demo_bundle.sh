#!/usr/bin/env bash
# Build the deployment bundle for the public judge demo.
#
# One Lambda serves both the API and the built web app, so this assembles exactly
# three things into build/demo-lambda/:
#
#   1. the `pool` package               — the application itself
#   2. its runtime dependencies         — resolved for Lambda's platform, not this Mac
#   3. apps/web/dist as web/            — the SPA, served from the same origin
#
# Why this script exists at all: `lambda_.Code.from_asset(<source dir>)` zips a
# directory as-is. For a Python function whose dependencies are not vendored, that
# produces a package that imports nothing and fails at cold start — and if a local
# .venv happens to sit in that directory, it also blows the 250 MB unzipped limit.
#
# Docker is deliberately not required. `uv --python-platform` resolves manylinux
# wheels from macOS, which keeps `make` runnable on the machine this project is
# actually built on.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/build/demo-lambda"
AGENT="$ROOT/services/agent"
WEB_DIST="$ROOT/apps/web/dist"

# Must match the runtime in infra/demo_app.py. A mismatch here produces wheels the
# deployed function cannot import, which surfaces as a cold-start crash rather than a
# build error — so it is asserted by infra/test_demo_stack.py.
PY_VERSION="3.13"
PLATFORM="x86_64-manylinux2014"

echo "→ Cleaning $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"

echo "→ Installing runtime dependencies for linux/$PLATFORM, python $PY_VERSION"
# Only what the API Lambda actually imports. `bedrock-agentcore` and
# `aws-opentelemetry-distro` are for the AgentCore container and would add tens of MB
# here for nothing. boto3 is vendored rather than inherited from the Lambda runtime so
# the `bedrock-agentcore` client model is guaranteed present, not merely likely.
uv pip install \
  --quiet \
  --python-platform "$PLATFORM" \
  --python-version "$PY_VERSION" \
  --only-binary=:all: \
  --target "$OUT" \
  "strands-agents>=1.52.0" \
  "boto3>=1.40.0" \
  "fastapi>=0.115.0" \
  "pydantic>=2.9.0" \
  "mangum>=0.19.0"

echo "→ Copying the pool package"
rsync -a --quiet \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.pytest_cache' --exclude '.ruff_cache' \
  "$AGENT/pool/" "$OUT/pool/"

if [[ ! -d "$WEB_DIST" ]]; then
  echo "✗ $WEB_DIST is missing. Run: npm run build --prefix apps/web" >&2
  exit 1
fi
echo "→ Copying the built web app"
mkdir -p "$OUT/web"
rsync -a --quiet "$WEB_DIST/" "$OUT/web/"

# Anything that could carry a credential must not be in a zip that goes to AWS and
# lands in the CDK staging bucket. Cheap to check, expensive to discover later.
#
# Two passes, because the bundle is mostly other people's code. File *names* are
# checked everywhere: a .env or an .aws directory has no business in a wheel either.
# File *contents* are checked only in the parts this project wrote — third-party
# packages ship documentation keys (botocore's AKIA…EXAMPLE) and CA bundles
# (botocore/cacert.pem, certifi/cacert.pem), and treating those as findings trains
# everyone to ignore the check.
echo "→ Checking the bundle for stray credentials and local state"
STRAY=$(find "$OUT" \( \
  -name '.env' -o -name '.env.*' -o -name 'credentials' -o -name '.aws' -o \
  -name '.venv' -o -name '.git' -o -name 'id_rsa' -o -name '*.p12' \) -print)
if [[ -n "$STRAY" ]]; then
  echo "✗ refusing to ship:" >&2
  echo "$STRAY" >&2
  exit 1
fi

bash "$ROOT/scripts/scan_authored.sh" "$OUT/pool" "$OUT/web"

UNZIPPED=$(du -sm "$OUT" | cut -f1)
echo "→ Bundle: ${UNZIPPED} MB unzipped (Lambda limit: 250 MB)"
if (( UNZIPPED > 240 )); then
  echo "✗ bundle is too close to the Lambda unzipped limit" >&2
  exit 1
fi

# Prove the two imports the deployed function makes at cold start would resolve, and
# that the vendored boto3 really does know the AgentCore data plane.
echo "→ Verifying the bundle imports"
find "$OUT" -maxdepth 1 -name 'mangum' -type d -o -maxdepth 1 -name 'fastapi' -type d \
  | grep -q . || { echo "✗ dependencies missing from the bundle" >&2; exit 1; }
test -f "$OUT/pool/api/app.py" || { echo "✗ pool package missing" >&2; exit 1; }
test -f "$OUT/web/index.html" || { echo "✗ web app missing" >&2; exit 1; }
grep -q "bedrock-agentcore" "$OUT/botocore/data/endpoints.json" 2>/dev/null \
  || test -d "$OUT/botocore/data/bedrock-agentcore" \
  || { echo "✗ vendored botocore has no bedrock-agentcore service model" >&2; exit 1; }

echo "✓ $OUT"
