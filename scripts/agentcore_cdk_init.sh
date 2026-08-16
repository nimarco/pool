#!/usr/bin/env bash
# Reconstruct agentcore/cdk/ — the CDK app the AgentCore CLI deploys through.
#
# WHY THIS SCRIPT EXISTS
#
# `agentcore deploy` requires a CDK project at agentcore/cdk/. The only official way to
# create one is `agentcore create`, which scaffolds a *whole new project*: it writes its
# own agentcore.json, aws-targets.json, and an app/<AgentName>/main.py agent. Running it
# here would overwrite Pool's configuration and drop a replacement agent next to the real
# coordinator. There is no `agentcore init-cdk`, and `agentcore import` only adopts
# already-deployed AWS resources or a legacy starter-toolkit project — neither applies.
#
# So we take the same assets `agentcore create` would use, from the installed CLI itself,
# and put them exactly where the CLI looks for them. The assets are shipped inside the
# npm package and contain no template placeholders — they are byte-identical whoever
# copies them — so this is deterministic rather than a hand-written approximation.
#
# The result stays generated and gitignored, per the CLI's own project convention. It is
# rebuilt from the CLI, never committed, so a fresh clone runs one documented command.
set -euo pipefail
cd "$(dirname "$0")/.."

# The CLI version this repository has been verified against. A newer CLI may ship
# different CDK assets, which is worth knowing about rather than discovering at deploy
# time — so a mismatch warns loudly but does not block.
EXPECTED_CLI_VERSION="0.27.0"
DEST="agentcore/cdk"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

if ! command -v agentcore >/dev/null 2>&1; then
  echo "✗ The AgentCore CLI is not installed." >&2
  echo "  npm install -g @aws/agentcore" >&2
  exit 1
fi

INSTALLED_VERSION="$(agentcore --version 2>/dev/null | tr -d '[:space:]')"

# Locate the installed package. `npm root -g` is the normal answer; resolving the
# `agentcore` executable's symlink also covers nvm, volta, and prefix-relocated installs
# where the global root is not where the binary appears to live.
PKG=""
NPM_ROOT="$(npm root -g 2>/dev/null || true)"
if [[ -n "$NPM_ROOT" && -d "$NPM_ROOT/@aws/agentcore/dist/assets/cdk" ]]; then
  PKG="$NPM_ROOT/@aws/agentcore"
else
  BIN="$(command -v agentcore)"
  # Follow one symlink level, then walk up from dist/cli/index.mjs to the package root.
  TARGET="$(readlink "$BIN" || echo "$BIN")"
  case "$TARGET" in
    /*) RESOLVED="$TARGET" ;;
    *)  RESOLVED="$(cd "$(dirname "$BIN")" && cd "$(dirname "$TARGET")" && pwd)/$(basename "$TARGET")" ;;
  esac
  CANDIDATE="$(cd "$(dirname "$RESOLVED")/../.." && pwd)"
  [[ -d "$CANDIDATE/dist/assets/cdk" ]] && PKG="$CANDIDATE"
fi

if [[ -z "$PKG" ]]; then
  echo "✗ Found the 'agentcore' command but not its bundled CDK assets." >&2
  echo "  Looked in: ${NPM_ROOT:-<npm root -g failed>}/@aws/agentcore" >&2
  echo "  Reinstall with: npm install -g @aws/agentcore" >&2
  exit 1
fi

SRC="$PKG/dist/assets/cdk"

echo "→ AgentCore CLI $INSTALLED_VERSION"
echo "  assets: $SRC"
if [[ "$INSTALLED_VERSION" != "$EXPECTED_CLI_VERSION" ]]; then
  echo "⚠ This repository was verified against CLI $EXPECTED_CLI_VERSION."
  echo "  The bundled CDK assets may differ. Re-run 'make agent-dry-run' and check the"
  echo "  synthesized resource set before deploying, then update EXPECTED_CLI_VERSION."
fi

# Never clobber silently. If the directory is already there it may hold an installed
# node_modules, a local edit, or a half-finished deploy — all of which are the operator's
# to discard, not this script's.
if [[ -e "$DEST" ]]; then
  if [[ $FORCE -eq 0 ]]; then
    echo "✓ $DEST already exists — nothing to do."
    echo "  To rebuild it from the installed CLI: rm -rf $DEST && $0"
    echo "  (or re-run with --force)"
    exit 0
  fi
  echo "→ --force: removing existing $DEST"
  rm -rf "$DEST"
fi

echo "→ Copying CDK assets into $DEST"
mkdir -p "$DEST"
cp -R "$SRC"/. "$DEST"/
# The package ships these under neutral names so npm does not apply them to itself.
[[ -f "$DEST/gitignore.template" ]] && mv "$DEST/gitignore.template" "$DEST/.gitignore"
[[ -f "$DEST/npmignore.template" ]] && mv "$DEST/npmignore.template" "$DEST/.npmignore"

echo "→ Installing CDK project dependencies (npm install)"
( cd "$DEST" && npm install --no-fund --no-audit )

echo "✓ $DEST reconstructed. Next: make agent-validate && make agent-dry-run"
