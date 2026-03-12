#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/my-api}"
FRONTEND_ENV="${FRONTEND_ENV:-/etc/my-api/frontend.env}"
RELEASE_ID="${1:?release id is required}"
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_ID"
CURRENT_LINK="$APP_ROOT/current"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
LOG_DIR="${LOG_DIR:-/var/log/my-api}"

mkdir -p "$LOG_DIR" "$APP_ROOT/releases" "$APP_ROOT/backups/sqlite"
touch "$LOG_DIR/update.log"
exec >>"$LOG_DIR/update.log" 2>&1

alert_failure() {
  "$RELEASE_DIR/scripts/send_alert.sh" "Release activation failed" "release=$RELEASE_ID host=$(hostname)" || true
}

trap alert_failure ERR

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] starting release activation: $RELEASE_ID"

if [[ ! -d "$RELEASE_DIR" ]]; then
  echo "release directory not found: $RELEASE_DIR" >&2
  exit 1
fi

cd "$APP_ROOT"
./.venv/bin/pip install -r "$RELEASE_DIR/backend/requirements.txt"

cd "$RELEASE_DIR/frontend"
set -a
. "$FRONTEND_ENV"
set +a
npm ci --include=dev
npm run build

ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"

sudo systemctl restart personal-api-admin-backend
for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1

sudo systemctl restart personal-api-admin-frontend
for _ in {1..30}; do
  if curl -fsS -I http://127.0.0.1:3000/login >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS -I http://127.0.0.1:3000/login >/dev/null 2>&1

find "$APP_ROOT/releases" -mindepth 1 -maxdepth 1 -type d | sort | head -n -"${KEEP_RELEASES}" | xargs -r rm -rf

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] release activated: $RELEASE_ID"
