#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/my-api}"
FRONTEND_ENV="${FRONTEND_ENV:-/etc/my-api/frontend.env}"
BACKEND_ENV="${BACKEND_ENV:-/etc/my-api/backend.env}"
RELEASE_ID="${1:?release id is required}"
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_ID"
CURRENT_LINK="$APP_ROOT/current"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
LOG_DIR="${LOG_DIR:-/var/log/my-api}"
RELEASE_META_FILE="$RELEASE_DIR/.release-meta.json"
MARKET_API_BIND_HOST="${MARKET_API_BIND_HOST:-127.0.0.1}"
MARKET_API_PORT="${MARKET_API_PORT:-8100}"

CURRENT_BEFORE="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
LAST_COMPLETED_STEP="bootstrap"
LAST_FAILED_STEP=""
ALERT_TITLE="Release activation failed"
ALERT_KIND="release_activation"
RELEASE_GIT_SHA="unknown"
RELEASE_BUILT_AT="unknown"

mkdir -p "$LOG_DIR" "$APP_ROOT/releases" "$APP_ROOT/backups/sqlite"
touch "$LOG_DIR/update.log"
exec >>"$LOG_DIR/update.log" 2>&1

timestamp() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

log() {
  echo "[$(timestamp)] $*"
}

read_release_meta_field() {
  local field="$1"
  python3 - <<'PY' "$RELEASE_META_FILE" "$field"
import json
import pathlib
import sys

meta_path = pathlib.Path(sys.argv[1])
field = sys.argv[2]
payload = json.loads(meta_path.read_text(encoding="utf-8"))
value = payload.get(field)
if not isinstance(value, str) or not value.strip():
    raise SystemExit(f"missing release metadata field: {field}")
print(value.strip())
PY
}

alert_failure() {
  local current_after
  local body

  if [[ ! -x "$RELEASE_DIR/scripts/send_alert.sh" ]]; then
    return 0
  fi

  current_after="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
  body="$(cat <<EOF
release_id=$RELEASE_ID
git_sha=$RELEASE_GIT_SHA
built_at=$RELEASE_BUILT_AT
host=$(hostname)
current_before=${CURRENT_BEFORE:-unknown}
current_after=${current_after:-unknown}
last_completed_step=$LAST_COMPLETED_STEP
failed_step=${LAST_FAILED_STEP:-unknown}
alert_kind=$ALERT_KIND
EOF
)"
  "$RELEASE_DIR/scripts/send_alert.sh" "$ALERT_TITLE" "$body" || true
}

trap alert_failure ERR

verify_with_retry() {
  local step="$1"
  local attempts="$2"
  local delay_seconds="$3"
  shift 3

  LAST_FAILED_STEP="$step"
  ALERT_TITLE="Deployment verification failed"
  ALERT_KIND="deployment_verification"

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if "$@"; then
      LAST_COMPLETED_STEP="$step"
      LAST_FAILED_STEP=""
      log "step:ok $step"
      return 0
    fi
    sleep "$delay_seconds"
  done

  return 1
}

check_backend_healthz() {
  curl -fsS http://127.0.0.1:8000/healthz >/dev/null
}

check_backend_version() {
  local response

  response="$(curl -fsS http://127.0.0.1:8000/version)" || return 1

  python3 - <<'PY' "$response" "$RELEASE_GIT_SHA" "$RELEASE_ID" "$RELEASE_BUILT_AT"
import json
import sys

payload = json.loads(sys.argv[1])
expected_git_sha = sys.argv[2]
expected_release_id = sys.argv[3]
expected_built_at = sys.argv[4]

if payload.get("status") != "ok":
    raise SystemExit("backend version endpoint is not healthy")
if payload.get("git_sha") != expected_git_sha:
    raise SystemExit("backend git_sha does not match release metadata")
if payload.get("release_id") != expected_release_id:
    raise SystemExit("backend release_id does not match release metadata")
if payload.get("built_at") != expected_built_at:
    raise SystemExit("backend built_at does not match release metadata")
PY
}

check_frontend_login() {
  curl -fsS -I http://127.0.0.1:3000/login >/dev/null
}

check_market_api_healthz() {
  curl -fsS "http://${MARKET_API_BIND_HOST}:${MARKET_API_PORT}/healthz" >/dev/null
}

run_n8n_verification() {
  local exit_code=0
  local environment_name="production"

  if [[ -r "$BACKEND_ENV" ]]; then
    set -a
    . "$BACKEND_ENV"
    set +a
    environment_name="${ENVIRONMENT:-production}"
  fi

  set +e
  "$RELEASE_DIR/scripts/check_n8n_dns.sh"
  exit_code=$?
  set -e

  case "$exit_code" in
    0)
      LAST_COMPLETED_STEP="n8n verification"
      LAST_FAILED_STEP=""
      log "step:ok n8n verification"
      return 0
      ;;
    10)
      LAST_COMPLETED_STEP="n8n verification"
      LAST_FAILED_STEP=""
      log "step:warn n8n verification container_missing"
      return 0
      ;;
    20)
      ALERT_TITLE="Transient DNS failure"
      ALERT_KIND="n8n_dns_failure"
      ;;
    21)
      ALERT_TITLE="App check failed"
      ALERT_KIND="n8n_ops_check_failure"
      ;;
    *)
      ALERT_TITLE="Deployment verification failed"
      ALERT_KIND="deployment_verification"
      ;;
  esac

  LAST_FAILED_STEP="n8n verification"

  if [[ "$environment_name" != "production" ]]; then
    LAST_COMPLETED_STEP="n8n verification"
    LAST_FAILED_STEP=""
    log "step:warn n8n verification skipped_failure exit_code=$exit_code environment=$environment_name"
    return 0
  fi

  return "$exit_code"
}

log "starting release activation: $RELEASE_ID"

if [[ ! -d "$RELEASE_DIR" ]]; then
  echo "release directory not found: $RELEASE_DIR" >&2
  exit 1
fi

if [[ ! -f "$RELEASE_META_FILE" ]]; then
  echo "release metadata not found: $RELEASE_META_FILE" >&2
  exit 1
fi

RELEASE_GIT_SHA="$(read_release_meta_field git_sha)"
RELEASE_BUILT_AT="$(read_release_meta_field built_at)"

LAST_FAILED_STEP="install backend dependencies"
cd "$APP_ROOT"
./.venv/bin/pip install -r "$RELEASE_DIR/backend/requirements.txt"
LAST_COMPLETED_STEP="install backend dependencies"
LAST_FAILED_STEP=""
log "step:ok install backend dependencies"

LAST_FAILED_STEP="build frontend"
cd "$RELEASE_DIR/frontend"
set -a
. "$FRONTEND_ENV"
set +a
npm ci --include=dev
npm run build
LAST_COMPLETED_STEP="build frontend"
LAST_FAILED_STEP=""
log "step:ok build frontend"

ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
LAST_COMPLETED_STEP="switch current symlink"
log "step:ok switch current symlink"

LAST_FAILED_STEP="restart backend"
sudo systemctl restart personal-api-admin-backend
LAST_COMPLETED_STEP="restart backend"
LAST_FAILED_STEP=""
log "step:ok restart backend"

verify_with_retry "backend healthz" 30 1 check_backend_healthz
verify_with_retry "backend version" 30 1 check_backend_version

LAST_FAILED_STEP="restart frontend"
sudo systemctl restart personal-api-admin-frontend
LAST_COMPLETED_STEP="restart frontend"
LAST_FAILED_STEP=""
log "step:ok restart frontend"

verify_with_retry "frontend login" 30 1 check_frontend_login

LAST_FAILED_STEP="restart market_api"
sudo systemctl restart personal-market-api
LAST_COMPLETED_STEP="restart market_api"
LAST_FAILED_STEP=""
log "step:ok restart market_api"

verify_with_retry "market_api healthz" 30 1 check_market_api_healthz
run_n8n_verification

find "$APP_ROOT/releases" -mindepth 1 -maxdepth 1 -type d | sort | head -n -"${KEEP_RELEASES}" | xargs -r rm -rf

LAST_COMPLETED_STEP="cleanup old releases"
log "step:ok cleanup old releases"
log "release activated: $RELEASE_ID"
