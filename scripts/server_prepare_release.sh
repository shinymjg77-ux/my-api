#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPS_ENV="${OPS_ENV:-/etc/my-api/ops.env}"
APP_ROOT="${APP_ROOT:-/srv/my-api}"
REPO_DIR="${RELEASE_REPO_DIR:-$REPO_ROOT}"
N8N_COMPOSE_PATH="${N8N_COMPOSE_PATH:-/opt/n8n/docker-compose.yml}"
TARGET_REF="${1:-origin/main}"
DEPLOY_MODE="${2:-${DEPLOY_MODE:-full}}"
RELEASE_ID="${RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_ID"
RELEASE_META_FILE="$RELEASE_DIR/.release-meta.json"
RELEASE_REPO_URL="${RELEASE_REPO_URL:-}"

if [[ -r "$OPS_ENV" ]]; then
  set -a
  . "$OPS_ENV"
  set +a
  REPO_DIR="${RELEASE_REPO_DIR:-$REPO_DIR}"
  N8N_COMPOSE_PATH="${N8N_COMPOSE_PATH:-$N8N_COMPOSE_PATH}"
  RELEASE_REPO_URL="${RELEASE_REPO_URL:-$RELEASE_REPO_URL}"
fi

ensure_repo_checkout() {
  if [[ -d "$REPO_DIR/.git" ]]; then
    return 0
  fi

  if [[ -z "$RELEASE_REPO_URL" ]]; then
    echo "repo checkout missing at $REPO_DIR and RELEASE_REPO_URL is not set" >&2
    exit 1
  fi

  mkdir -p "$(dirname "$REPO_DIR")"
  git clone "$RELEASE_REPO_URL" "$REPO_DIR"
}

write_release_meta() {
  local commit_sha="$1"
  local built_at="$2"

  python3 - <<'PY' "$commit_sha" "$RELEASE_ID" "$built_at" >"$RELEASE_META_FILE"
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
}

update_release_meta_n8n_hash() {
  local n8n_hash="$1"

  python3 - <<'PY' "$RELEASE_META_FILE" "$n8n_hash"
import json
import pathlib
import sys

meta_path = pathlib.Path(sys.argv[1])
payload = json.loads(meta_path.read_text(encoding="utf-8"))
payload["n8n_compose_sha256"] = sys.argv[2]
meta_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

case "$DEPLOY_MODE" in
  full|backend)
    ;;
  *)
    echo "unsupported deploy mode: $DEPLOY_MODE" >&2
    exit 1
    ;;
esac

echo "[server-deploy] preparing ref=$TARGET_REF release=$RELEASE_ID mode=$DEPLOY_MODE repo=$REPO_DIR"

ensure_repo_checkout
git -C "$REPO_DIR" fetch --prune origin

COMMIT_SHA="$(git -C "$REPO_DIR" rev-parse "$TARGET_REF^{commit}")"
BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ -e "$RELEASE_DIR" ]]; then
  echo "release directory already exists: $RELEASE_DIR" >&2
  exit 1
fi

mkdir -p "$APP_ROOT/releases" "$APP_ROOT/backups/sqlite" "$APP_ROOT/data" "$RELEASE_DIR"
git -C "$REPO_DIR" archive "$COMMIT_SHA" | tar -x -C "$RELEASE_DIR"
write_release_meta "$COMMIT_SHA" "$BUILT_AT"
chmod +x "$RELEASE_DIR"/scripts/*.sh

"$RELEASE_DIR/scripts/sync_n8n_config.sh" "$RELEASE_DIR"
N8N_COMPOSE_SHA256="$(python3 - <<'PY' "$N8N_COMPOSE_PATH"
import hashlib
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
)"
update_release_meta_n8n_hash "$N8N_COMPOSE_SHA256"
bash "$RELEASE_DIR/scripts/remote_activate_release.sh" "$RELEASE_ID" "$DEPLOY_MODE"

echo "[server-deploy] activated release=$RELEASE_ID mode=$DEPLOY_MODE git_sha=$COMMIT_SHA"
