#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_HOST="${1:?usage: ./scripts/deploy_from_server.sh <ssh-host-alias-or-hostname> [git-ref-or-sha] [full|backend]}"
TARGET_REF="${2:-origin/main}"
DEPLOY_MODE="${3:-${DEPLOY_MODE:-full}}"
SERVER_REPO_DIR="${RELEASE_REPO_DIR:-/srv/my-api/repo}"
APP_ROOT="${APP_ROOT:-/srv/my-api}"
RELEASE_REPO_URL="${RELEASE_REPO_URL:-$(git -C "$REPO_ROOT" remote get-url origin)}"
REMOTE_REF="$(printf '%q' "$TARGET_REF")"
REMOTE_MODE="$(printf '%q' "$DEPLOY_MODE")"
REMOTE_REPO_DIR="$(printf '%q' "$SERVER_REPO_DIR")"
REMOTE_APP_ROOT="$(printf '%q' "$APP_ROOT")"
REMOTE_REPO_URL="$(printf '%q' "$RELEASE_REPO_URL")"

ssh "$TARGET_HOST" "tmp_script=\$(mktemp /tmp/my-api-server-prepare.XXXXXX.sh) && cat >\"\$tmp_script\" && chmod +x \"\$tmp_script\" && APP_ROOT=$REMOTE_APP_ROOT RELEASE_REPO_DIR=$REMOTE_REPO_DIR RELEASE_REPO_URL=$REMOTE_REPO_URL bash \"\$tmp_script\" $REMOTE_REF $REMOTE_MODE; rm -f \"\$tmp_script\"" <"$SCRIPT_DIR/server_prepare_release.sh"
