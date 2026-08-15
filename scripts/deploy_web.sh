#!/usr/bin/env bash
# Upload the built web app and invalidate the CDN.
set -euo pipefail
STACK="${POOL_STACK_NAME:-PoolStack}"

BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='WebBucket'].OutputValue" --output text)
API=$(aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)

echo "→ Rebuilding the web app against $API"
VITE_API_BASE="${API%/}" npm run build --prefix apps/web

echo "→ Syncing to s3://$BUCKET"
aws s3 sync apps/web/dist "s3://$BUCKET" --delete

DIST=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='Pool demo web app'].Id | [0]" --output text)
if [[ -n "$DIST" && "$DIST" != "None" ]]; then
  echo "→ Invalidating CloudFront $DIST"
  aws cloudfront create-invalidation --distribution-id "$DIST" --paths '/*' >/dev/null
fi
echo "✓ deployed"
