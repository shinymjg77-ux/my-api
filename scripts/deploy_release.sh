#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${1:?usage: ./scripts/deploy_release.sh <ssh-host-alias-or-hostname>}"
APP_ROOT="${APP_ROOT:-/srv/my-api}"
RELEASE_ID="${RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_ID"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GIT_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RELEASE_META_FILE="$(mktemp)"

cleanup() {
  rm -f "$RELEASE_META_FILE"
}

trap cleanup EXIT

python3 - <<'PY' "$GIT_SHA" "$RELEASE_ID" "$BUILT_AT" >"$RELEASE_META_FILE"
import json
import sys

print(
    json.dumps(
        {
            "git_sha": sys.argv[1],
            "release_id": sys.argv[2],
            "built_at": sys.argv[3],
        },
        indent=2,
    )
)
PY

echo "[deploy] target=$TARGET_HOST release=$RELEASE_ID git_sha=$GIT_SHA built_at=$BUILT_AT"

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

rsync -az "$RELEASE_META_FILE" "$TARGET_HOST:$RELEASE_DIR/.release-meta.json"

ssh "$TARGET_HOST" "chmod +x '$RELEASE_DIR'/scripts/*.sh"
ssh "$TARGET_HOST" "bash '$RELEASE_DIR/scripts/remote_activate_release.sh' '$RELEASE_ID'"

echo "[deploy] completed release=$RELEASE_ID"
