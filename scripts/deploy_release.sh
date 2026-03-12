#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${1:?usage: ./scripts/deploy_release.sh <ssh-host-alias-or-hostname>}"
APP_ROOT="${APP_ROOT:-/srv/my-api}"
RELEASE_ID="${RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_ID"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[deploy] target=$TARGET_HOST release=$RELEASE_ID"

ssh "$TARGET_HOST" "mkdir -p '$APP_ROOT/releases' '$APP_ROOT/backups/sqlite' '$APP_ROOT/data' /var/log/my-api"

rsync -az \
  --delete \
  --exclude '.git' \
  --exclude '.env' \
  --exclude '.omx' \
  --exclude '.venv' \
  --exclude 'data' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/.next' \
  "$REPO_ROOT/" "$TARGET_HOST:$RELEASE_DIR/"

ssh "$TARGET_HOST" "chmod +x '$RELEASE_DIR'/scripts/*.sh"
ssh "$TARGET_HOST" "bash '$RELEASE_DIR/scripts/remote_activate_release.sh' '$RELEASE_ID'"

echo "[deploy] completed release=$RELEASE_ID"
