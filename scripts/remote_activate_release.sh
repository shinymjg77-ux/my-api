#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/my-api}"
OPS_ENV="${OPS_ENV:-/etc/my-api/ops.env}"
FRONTEND_ENV="${FRONTEND_ENV:-/etc/my-api/frontend.env}"
BACKEND_ENV="${BACKEND_ENV:-/etc/my-api/backend.env}"
RELEASE_ID="${1:?release id is required}"
DEPLOY_MODE="${2:-${DEPLOY_MODE:-full}}"
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_ID"
CURRENT_LINK="$APP_ROOT/current"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
LOG_DIR="${LOG_DIR:-/var/log/my-api}"
RELEASE_META_FILE="$RELEASE_DIR/.release-meta.json"
MARKET_API_BIND_HOST="${MARKET_API_BIND_HOST:-127.0.0.1}"
MARKET_API_PORT="${MARKET_API_PORT:-8100}"
BACKEND_STABLE_BASE_URL="${BACKEND_STABLE_BASE_URL:-http://127.0.0.1:9000}"
BACKEND_UPSTREAM_CONF="${BACKEND_UPSTREAM_CONF:-/etc/nginx/snippets/my-api-backend-upstream.conf}"
BACKEND_ACTIVE_SLOT_STATE_PATH="${BACKEND_ACTIVE_SLOT_STATE_PATH:-$APP_ROOT/state/backend-active-slot}"
BACKEND_SLOT_ROOT="${BACKEND_SLOT_ROOT:-$APP_ROOT/slots}"
BACKEND_SLOT_ENV_DIR="${BACKEND_SLOT_ENV_DIR:-/etc/my-api/backend-slots}"
BACKEND_SLOTS="${BACKEND_SLOTS:-blue,green}"
FRONTEND_STABLE_BASE_URL="${FRONTEND_STABLE_BASE_URL:-http://127.0.0.1:3100}"
FRONTEND_UPSTREAM_CONF="${FRONTEND_UPSTREAM_CONF:-/etc/nginx/snippets/my-api-frontend-upstream.conf}"
FRONTEND_ACTIVE_SLOT_STATE_PATH="${FRONTEND_ACTIVE_SLOT_STATE_PATH:-$APP_ROOT/state/frontend-active-slot}"
FRONTEND_SLOT_ROOT="${FRONTEND_SLOT_ROOT:-$APP_ROOT/slots}"
FRONTEND_SLOT_ENV_DIR="${FRONTEND_SLOT_ENV_DIR:-/etc/my-api/frontend-slots}"
FRONTEND_SLOTS="${FRONTEND_SLOTS:-blue,green}"
SYSTEMD_UNIT_DIR="${SYSTEMD_UNIT_DIR:-/etc/systemd/system}"

if [[ -r "$OPS_ENV" ]]; then
  set -a
  . "$OPS_ENV"
  set +a
  BACKEND_STABLE_BASE_URL="${BACKEND_STABLE_BASE_URL:-http://127.0.0.1:9000}"
  BACKEND_UPSTREAM_CONF="${BACKEND_UPSTREAM_CONF:-/etc/nginx/snippets/my-api-backend-upstream.conf}"
  BACKEND_ACTIVE_SLOT_STATE_PATH="${BACKEND_ACTIVE_SLOT_STATE_PATH:-$APP_ROOT/state/backend-active-slot}"
  BACKEND_SLOT_ROOT="${BACKEND_SLOT_ROOT:-$APP_ROOT/slots}"
  BACKEND_SLOT_ENV_DIR="${BACKEND_SLOT_ENV_DIR:-/etc/my-api/backend-slots}"
  BACKEND_SLOTS="${BACKEND_SLOTS:-blue,green}"
  FRONTEND_STABLE_BASE_URL="${FRONTEND_STABLE_BASE_URL:-http://127.0.0.1:3100}"
  FRONTEND_UPSTREAM_CONF="${FRONTEND_UPSTREAM_CONF:-/etc/nginx/snippets/my-api-frontend-upstream.conf}"
  FRONTEND_ACTIVE_SLOT_STATE_PATH="${FRONTEND_ACTIVE_SLOT_STATE_PATH:-$APP_ROOT/state/frontend-active-slot}"
  FRONTEND_SLOT_ROOT="${FRONTEND_SLOT_ROOT:-$APP_ROOT/slots}"
  FRONTEND_SLOT_ENV_DIR="${FRONTEND_SLOT_ENV_DIR:-/etc/my-api/frontend-slots}"
  FRONTEND_SLOTS="${FRONTEND_SLOTS:-blue,green}"
fi

CURRENT_BEFORE="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
LAST_COMPLETED_STEP="bootstrap"
LAST_FAILED_STEP=""
ALERT_TITLE="Release activation failed"
ALERT_KIND="release_activation"
RELEASE_GIT_SHA="unknown"
RELEASE_BUILT_AT="unknown"
CURRENT_BACKEND_SLOT=""
TARGET_BACKEND_SLOT=""
TARGET_BACKEND_PORT=""
PREVIOUS_BACKEND_PORT=""
BACKEND_SWITCH_APPLIED=false
CURRENT_FRONTEND_SLOT=""
TARGET_FRONTEND_SLOT=""
TARGET_FRONTEND_PORT=""
PREVIOUS_FRONTEND_PORT=""
PREVIOUS_FRONTEND_SLOT=""
FRONTEND_SWITCH_APPLIED=false
SYSTEMD_UNITS_SYNCED=false
DRIFT_TIMER_WAS_ACTIVE=false
DRIFT_TIMER_WAS_ENABLED=false

timestamp() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

log() {
  echo "[$(timestamp)] $*"
}

record_drift_timer_state() {
  if sudo systemctl is-active --quiet my-api-drift-check.timer; then
    DRIFT_TIMER_WAS_ACTIVE=true
  fi

  if sudo systemctl is-enabled --quiet my-api-drift-check.timer; then
    DRIFT_TIMER_WAS_ENABLED=true
  fi
}

validate_mode() {
  case "$DEPLOY_MODE" in
    full|backend)
      ;;
    *)
      echo "unsupported deploy mode: $DEPLOY_MODE" >&2
      exit 1
      ;;
  esac
}

normalize_base_url() {
  printf '%s' "${1%/}"
}

slot_link_path() {
  local slot="$1"
  printf '%s/backend-%s' "$BACKEND_SLOT_ROOT" "$slot"
}

frontend_slot_link_path() {
  local slot="$1"
  printf '%s/frontend-%s' "$FRONTEND_SLOT_ROOT" "$slot"
}

slot_env_path() {
  local slot="$1"
  printf '%s/%s.env' "$BACKEND_SLOT_ENV_DIR" "$slot"
}

frontend_slot_env_path() {
  local slot="$1"
  printf '%s/%s.env' "$FRONTEND_SLOT_ENV_DIR" "$slot"
}

slot_default_port() {
  case "$1" in
    blue)
      echo "8001"
      ;;
    green)
      echo "8002"
      ;;
    *)
      echo "unsupported backend slot: $1" >&2
      exit 1
      ;;
  esac
}

frontend_slot_default_port() {
  case "$1" in
    blue)
      echo "3001"
      ;;
    green)
      echo "3002"
      ;;
    *)
      echo "unsupported frontend slot: $1" >&2
      exit 1
      ;;
  esac
}

active_backend_slot() {
  if [[ -r "$BACKEND_ACTIVE_SLOT_STATE_PATH" ]]; then
    local slot
    slot="$(tr -d '[:space:]' <"$BACKEND_ACTIVE_SLOT_STATE_PATH")"
    if [[ "$slot" == "blue" || "$slot" == "green" ]]; then
      echo "$slot"
      return 0
    fi
  fi

  echo "blue"
}

active_frontend_slot() {
  if [[ -r "$FRONTEND_ACTIVE_SLOT_STATE_PATH" ]]; then
    local slot
    slot="$(tr -d '[:space:]' <"$FRONTEND_ACTIVE_SLOT_STATE_PATH")"
    if [[ "$slot" == "blue" || "$slot" == "green" ]]; then
      echo "$slot"
      return 0
    fi
  fi

  echo "blue"
}

inactive_backend_slot() {
  case "$1" in
    blue)
      echo "green"
      ;;
    green)
      echo "blue"
      ;;
    *)
      echo "unsupported backend slot: $1" >&2
      exit 1
      ;;
  esac
}

inactive_frontend_slot() {
  case "$1" in
    blue)
      echo "green"
      ;;
    green)
      echo "blue"
      ;;
    *)
      echo "unsupported frontend slot: $1" >&2
      exit 1
      ;;
  esac
}

ensure_backend_slot_env() {
  local slot="$1"
  local path
  local port
  local temp_file

  path="$(slot_env_path "$slot")"
  port="$(slot_default_port "$slot")"

  sudo install -d -m 755 "$BACKEND_SLOT_ENV_DIR"
  if sudo test -f "$path"; then
    return 0
  fi

  temp_file="$(mktemp)"
  printf 'BACKEND_SLOT_PORT=%s\n' "$port" >"$temp_file"
  sudo install -m 644 "$temp_file" "$path"
  rm -f "$temp_file"
}

ensure_frontend_slot_env() {
  local slot="$1"
  local path
  local port
  local temp_file

  path="$(frontend_slot_env_path "$slot")"
  port="$(frontend_slot_default_port "$slot")"

  sudo install -d -m 755 "$FRONTEND_SLOT_ENV_DIR"
  if sudo test -f "$path"; then
    return 0
  fi

  temp_file="$(mktemp)"
  printf 'FRONTEND_SLOT_PORT=%s\n' "$port" >"$temp_file"
  sudo install -m 644 "$temp_file" "$path"
  rm -f "$temp_file"
}

slot_port_for() {
  local slot="$1"
  local path

  path="$(slot_env_path "$slot")"
  if [[ -r "$path" ]]; then
    grep '^BACKEND_SLOT_PORT=' "$path" | tail -n 1 | cut -d= -f2-
    return 0
  fi

  sudo python3 - <<'PY' "$path"
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key == "BACKEND_SLOT_PORT" and value.strip():
        print(value.strip())
        raise SystemExit(0)
raise SystemExit("missing BACKEND_SLOT_PORT")
PY
}

frontend_slot_port_for() {
  local slot="$1"
  local path

  path="$(frontend_slot_env_path "$slot")"
  if [[ -r "$path" ]]; then
    grep '^FRONTEND_SLOT_PORT=' "$path" | tail -n 1 | cut -d= -f2-
    return 0
  fi

  sudo python3 - <<'PY' "$path"
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key == "FRONTEND_SLOT_PORT" and value.strip():
        print(value.strip())
        raise SystemExit(0)
raise SystemExit("missing FRONTEND_SLOT_PORT")
PY
}

ensure_slot_link() {
  local slot="$1"
  local target_dir="$2"

  mkdir -p "$BACKEND_SLOT_ROOT"
  ln -sfn "$target_dir" "$(slot_link_path "$slot")"
}

ensure_frontend_slot_link() {
  local slot="$1"
  local target_dir="$2"

  mkdir -p "$FRONTEND_SLOT_ROOT"
  ln -sfn "$target_dir" "$(frontend_slot_link_path "$slot")"
}

record_active_backend_slot() {
  local slot="$1"

  mkdir -p "$(dirname "$BACKEND_ACTIVE_SLOT_STATE_PATH")"
  printf '%s\n' "$slot" >"$BACKEND_ACTIVE_SLOT_STATE_PATH"
}

record_active_frontend_slot() {
  local slot="$1"

  mkdir -p "$(dirname "$FRONTEND_ACTIVE_SLOT_STATE_PATH")"
  printf '%s\n' "$slot" >"$FRONTEND_ACTIVE_SLOT_STATE_PATH"
}

clear_active_frontend_slot() {
  rm -f "$FRONTEND_ACTIVE_SLOT_STATE_PATH"
}

current_upstream_port() {
  local path="$1"
  local fallback="$2"
  local port=""

  if [[ -r "$path" ]]; then
    port="$(grep -Eo 'http://127\.0\.0\.1:[0-9]+' "$path" | head -n 1 | cut -d: -f3 || true)"
    if [[ -n "$port" ]]; then
      printf '%s\n' "$port"
      return 0
    fi
  fi

  printf '%s\n' "$fallback"
}

release_meta_json_set() {
  local field="$1"
  local value="$2"

  python3 - <<'PY' "$RELEASE_META_FILE" "$field" "$value"
import json
import pathlib
import sys

meta_path = pathlib.Path(sys.argv[1])
field = sys.argv[2]
value = sys.argv[3]
payload = json.loads(meta_path.read_text(encoding="utf-8"))
payload[field] = value
meta_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
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

load_backend_runtime_env() {
  if [[ -r "$BACKEND_ENV" ]]; then
    set -a
    . "$BACKEND_ENV"
    set +a
    return 0
  fi

  if sudo test -r "$BACKEND_ENV"; then
    eval "$(
      sudo python3 - <<'PY' "$BACKEND_ENV"
import pathlib
import shlex
import sys

env_path = pathlib.Path(sys.argv[1])
values = {}
for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key in {"ENVIRONMENT", "JOB_SHARED_SECRET"}:
        values[key] = value

for key, value in values.items():
    print(f"export {key}={shlex.quote(value)}")
PY
    )"
  fi
}

sync_managed_systemd_units() {
  local units=(
    "my-api-alert@.service"
    "my-api-drift-check.service"
    "my-api-drift-check.timer"
    "personal-api-admin-backend.service"
    "personal-api-admin-backend@.service"
    "personal-api-admin-frontend.service"
    "personal-api-admin-frontend@.service"
    "personal-market-api.service"
  )
  local unit
  local source_path

  record_drift_timer_state

  for unit in "${units[@]}"; do
    source_path="$RELEASE_DIR/deploy/systemd/$unit"
    if [[ ! -f "$source_path" ]]; then
      echo "missing managed systemd unit in release: $source_path" >&2
      exit 1
    fi
    sudo install -m 644 "$source_path" "$SYSTEMD_UNIT_DIR/$unit"
  done

  sudo systemctl daemon-reload
  SYSTEMD_UNITS_SYNCED=true
}

restart_managed_timers_if_needed() {
  if [[ "$SYSTEMD_UNITS_SYNCED" != "true" ]]; then
    return 0
  fi

  if [[ "$DRIFT_TIMER_WAS_ACTIVE" == "true" || "$DRIFT_TIMER_WAS_ENABLED" == "true" ]]; then
    sudo systemctl restart my-api-drift-check.timer
    log "step:ok restart drift timer"
  fi
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
deploy_mode=$DEPLOY_MODE
host=$(hostname)
current_before=${CURRENT_BEFORE:-unknown}
current_after=${current_after:-unknown}
current_backend_slot=${CURRENT_BACKEND_SLOT:-unknown}
target_backend_slot=${TARGET_BACKEND_SLOT:-unknown}
current_frontend_slot=${CURRENT_FRONTEND_SLOT:-unknown}
target_frontend_slot=${TARGET_FRONTEND_SLOT:-unknown}
last_completed_step=$LAST_COMPLETED_STEP
failed_step=${LAST_FAILED_STEP:-unknown}
alert_kind=$ALERT_KIND
EOF
)"
  "$RELEASE_DIR/scripts/send_alert.sh" "$ALERT_TITLE" "$body" || true
}

rollback_backend_switch() {
  if [[ "$BACKEND_SWITCH_APPLIED" != "true" || -z "$CURRENT_BACKEND_SLOT" || -z "$PREVIOUS_BACKEND_PORT" ]]; then
    return 0
  fi

  write_backend_upstream_conf "$CURRENT_BACKEND_SLOT" "$PREVIOUS_BACKEND_PORT"
  sudo nginx -t
  sudo systemctl reload nginx
  record_active_backend_slot "$CURRENT_BACKEND_SLOT"
  BACKEND_SWITCH_APPLIED=false
  log "step:rollback backend switch slot=$CURRENT_BACKEND_SLOT port=$PREVIOUS_BACKEND_PORT"
}

rollback_frontend_switch() {
  if [[ "$FRONTEND_SWITCH_APPLIED" != "true" || -z "$PREVIOUS_FRONTEND_PORT" ]]; then
    return 0
  fi

  write_frontend_upstream_conf "${PREVIOUS_FRONTEND_SLOT:-legacy}" "$PREVIOUS_FRONTEND_PORT"
  sudo nginx -t
  sudo systemctl reload nginx
  if [[ -n "$PREVIOUS_FRONTEND_SLOT" ]]; then
    record_active_frontend_slot "$PREVIOUS_FRONTEND_SLOT"
  else
    clear_active_frontend_slot
  fi
  FRONTEND_SWITCH_APPLIED=false
  log "step:rollback frontend switch slot=${PREVIOUS_FRONTEND_SLOT:-legacy} port=$PREVIOUS_FRONTEND_PORT"
}

handle_failure() {
  rollback_frontend_switch || true
  rollback_backend_switch || true
  alert_failure || true
}

trap handle_failure ERR

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

check_backend_healthz_url() {
  local base_url
  base_url="$(normalize_base_url "$1")"
  curl -fsS "${base_url}/healthz" >/dev/null
}

check_backend_version_url() {
  local base_url
  local response

  base_url="$(normalize_base_url "$1")"
  response="$(curl -fsS "${base_url}/version")" || return 1

  python3 - <<'PY' "$response" "$RELEASE_GIT_SHA" "$RELEASE_ID" "$RELEASE_BUILT_AT" "$TARGET_BACKEND_SLOT"
import json
import sys

payload = json.loads(sys.argv[1])
expected_git_sha = sys.argv[2]
expected_release_id = sys.argv[3]
expected_built_at = sys.argv[4]
expected_backend_slot = sys.argv[5]

if payload.get("status") != "ok":
    raise SystemExit("backend version endpoint is not healthy")
if payload.get("git_sha") != expected_git_sha:
    raise SystemExit("backend git_sha does not match release metadata")
if payload.get("release_id") != expected_release_id:
    raise SystemExit("backend release_id does not match release metadata")
if payload.get("built_at") != expected_built_at:
    raise SystemExit("backend built_at does not match release metadata")
if payload.get("backend_slot") != expected_backend_slot:
    raise SystemExit("backend slot does not match release metadata")
PY
}

check_frontend_login_url() {
  local base_url
  base_url="$(normalize_base_url "$1")"
  curl -fsS -I "${base_url}/login" >/dev/null
}

check_frontend_runtime_version_url() {
  local base_url
  local response

  base_url="$(normalize_base_url "$1")"
  response="$(curl -fsS "${base_url}/api/runtime/version")" || return 1

  python3 - <<'PY' "$response" "$RELEASE_GIT_SHA" "$RELEASE_ID" "$RELEASE_BUILT_AT" "$TARGET_FRONTEND_SLOT"
import json
import sys

payload = json.loads(sys.argv[1])
expected_git_sha = sys.argv[2]
expected_release_id = sys.argv[3]
expected_built_at = sys.argv[4]
expected_frontend_slot = sys.argv[5]

if payload.get("status") != "ok":
    raise SystemExit("frontend runtime version endpoint is not healthy")
if payload.get("git_sha") != expected_git_sha:
    raise SystemExit("frontend git_sha does not match release metadata")
if payload.get("release_id") != expected_release_id:
    raise SystemExit("frontend release_id does not match release metadata")
if payload.get("built_at") != expected_built_at:
    raise SystemExit("frontend built_at does not match release metadata")
if payload.get("frontend_slot") != expected_frontend_slot:
    raise SystemExit("frontend slot does not match release metadata")
PY
}

check_market_api_healthz() {
  curl -fsS "http://${MARKET_API_BIND_HOST}:${MARKET_API_PORT}/healthz" >/dev/null
}

write_backend_upstream_conf() {
  local slot="$1"
  local port="$2"
  local temp_file

  temp_file="$(mktemp)"
  printf 'set $my_api_backend http://127.0.0.1:%s;\n' "$port" >"$temp_file"
  sudo install -d -m 755 "$(dirname "$BACKEND_UPSTREAM_CONF")"
  sudo install -m 644 "$temp_file" "$BACKEND_UPSTREAM_CONF"
  rm -f "$temp_file"
  log "step:ok write backend upstream slot=$slot port=$port"
}

write_frontend_upstream_conf() {
  local slot="$1"
  local port="$2"
  local temp_file

  temp_file="$(mktemp)"
  printf 'set $my_api_frontend http://127.0.0.1:%s;\n' "$port" >"$temp_file"
  sudo install -d -m 755 "$(dirname "$FRONTEND_UPSTREAM_CONF")"
  sudo install -m 644 "$temp_file" "$FRONTEND_UPSTREAM_CONF"
  rm -f "$temp_file"
  log "step:ok write frontend upstream slot=$slot port=$port"
}

ensure_slot_runtime() {
  local slot="$1"
  local slot_target="$2"
  local slot_port

  ensure_backend_slot_env "$slot"
  ensure_slot_link "$slot" "$slot_target"
  slot_port="$(slot_port_for "$slot")"
  sudo systemctl restart "personal-api-admin-backend@${slot}"
  verify_with_retry "backend slot ${slot} healthz" 30 1 check_backend_healthz_url "http://127.0.0.1:${slot_port}"
}

ensure_frontend_slot_runtime() {
  local slot="$1"
  local slot_target="$2"
  local slot_port

  ensure_frontend_slot_env "$slot"
  ensure_frontend_slot_link "$slot" "$slot_target"
  slot_port="$(frontend_slot_port_for "$slot")"
  sudo systemctl restart "personal-api-admin-frontend@${slot}"
  verify_with_retry "frontend slot ${slot} login" 30 1 check_frontend_login_url "http://127.0.0.1:${slot_port}"
}

run_n8n_verification() {
  local exit_code=0
  local environment_name="production"

  load_backend_runtime_env
  environment_name="${ENVIRONMENT:-production}"

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

cleanup_old_releases() {
  local protected=()
  local candidate

  for candidate in "$CURRENT_LINK" "$(slot_link_path blue)" "$(slot_link_path green)" "$(frontend_slot_link_path blue)" "$(frontend_slot_link_path green)"; do
    local resolved
    resolved="$(readlink -f "$candidate" 2>/dev/null || true)"
    if [[ -n "$resolved" ]]; then
      protected+=("$resolved")
    fi
  done

  mapfile -t all_releases < <(find "$APP_ROOT/releases" -mindepth 1 -maxdepth 1 -type d | sort)
  if (( ${#all_releases[@]} <= KEEP_RELEASES )); then
    return 0
  fi

  local delete_count=$(( ${#all_releases[@]} - KEEP_RELEASES ))
  local release_dir
  local skip=false

  for release_dir in "${all_releases[@]:0:delete_count}"; do
    skip=false
    for candidate in "${protected[@]}"; do
      if [[ "$release_dir" == "$candidate" ]]; then
        skip=true
        break
      fi
    done
    if [[ "$skip" == "true" ]]; then
      continue
    fi
    rm -rf "$release_dir"
  done
}

validate_mode
BACKEND_STABLE_BASE_URL="$(normalize_base_url "$BACKEND_STABLE_BASE_URL")"
FRONTEND_STABLE_BASE_URL="$(normalize_base_url "$FRONTEND_STABLE_BASE_URL")"

mkdir -p "$LOG_DIR" "$APP_ROOT/releases" "$APP_ROOT/backups/sqlite" "$APP_ROOT/data" "$BACKEND_SLOT_ROOT" "$FRONTEND_SLOT_ROOT" "$(dirname "$BACKEND_ACTIVE_SLOT_STATE_PATH")" "$(dirname "$FRONTEND_ACTIVE_SLOT_STATE_PATH")"
touch "$LOG_DIR/update.log"
exec >>"$LOG_DIR/update.log" 2>&1

log "starting release activation: $RELEASE_ID mode=$DEPLOY_MODE"

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
CURRENT_BACKEND_SLOT="$(active_backend_slot)"
TARGET_BACKEND_SLOT="$(inactive_backend_slot "$CURRENT_BACKEND_SLOT")"

LAST_FAILED_STEP="sync managed systemd units"
sync_managed_systemd_units
LAST_COMPLETED_STEP="sync managed systemd units"
LAST_FAILED_STEP=""
log "step:ok sync managed systemd units"

ensure_backend_slot_env blue
ensure_backend_slot_env green
TARGET_BACKEND_PORT="$(slot_port_for "$TARGET_BACKEND_SLOT")"
PREVIOUS_BACKEND_PORT="$(slot_port_for "$CURRENT_BACKEND_SLOT")"

if [[ "$DEPLOY_MODE" == "full" ]]; then
  CURRENT_FRONTEND_SLOT="$(active_frontend_slot)"
  TARGET_FRONTEND_SLOT="$(inactive_frontend_slot "$CURRENT_FRONTEND_SLOT")"
  ensure_frontend_slot_env blue
  ensure_frontend_slot_env green
  TARGET_FRONTEND_PORT="$(frontend_slot_port_for "$TARGET_FRONTEND_SLOT")"
  PREVIOUS_FRONTEND_PORT="$(current_upstream_port "$FRONTEND_UPSTREAM_CONF" "3000")"
  if [[ "$PREVIOUS_FRONTEND_PORT" == "$(frontend_slot_port_for blue)" ]]; then
    PREVIOUS_FRONTEND_SLOT="blue"
  elif [[ "$PREVIOUS_FRONTEND_PORT" == "$(frontend_slot_port_for green)" ]]; then
    PREVIOUS_FRONTEND_SLOT="green"
  fi
fi

LAST_FAILED_STEP="install backend dependencies"
cd "$APP_ROOT"
./.venv/bin/pip install -r "$RELEASE_DIR/backend/requirements.txt"
LAST_COMPLETED_STEP="install backend dependencies"
LAST_FAILED_STEP=""
log "step:ok install backend dependencies"

if [[ "$DEPLOY_MODE" == "full" ]]; then
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
fi

if [[ -n "$CURRENT_BEFORE" ]] && ! sudo systemctl is-active --quiet "personal-api-admin-backend@${CURRENT_BACKEND_SLOT}"; then
  LAST_FAILED_STEP="bootstrap current backend slot"
  ensure_slot_runtime "$CURRENT_BACKEND_SLOT" "$CURRENT_BEFORE"
  LAST_COMPLETED_STEP="bootstrap current backend slot"
  LAST_FAILED_STEP=""
  log "step:ok bootstrap current backend slot"
fi

LAST_FAILED_STEP="prepare target backend slot"
release_meta_json_set "backend_slot" "$TARGET_BACKEND_SLOT"
ensure_slot_link "$TARGET_BACKEND_SLOT" "$RELEASE_DIR"
LAST_COMPLETED_STEP="prepare target backend slot"
LAST_FAILED_STEP=""
log "step:ok prepare target backend slot"

LAST_FAILED_STEP="restart target backend slot"
sudo systemctl restart "personal-api-admin-backend@${TARGET_BACKEND_SLOT}"
LAST_COMPLETED_STEP="restart target backend slot"
LAST_FAILED_STEP=""
log "step:ok restart target backend slot"

verify_with_retry "target backend healthz" 30 1 check_backend_healthz_url "http://127.0.0.1:${TARGET_BACKEND_PORT}"
verify_with_retry "target backend version" 30 1 check_backend_version_url "http://127.0.0.1:${TARGET_BACKEND_PORT}"

LAST_FAILED_STEP="switch backend upstream"
write_backend_upstream_conf "$TARGET_BACKEND_SLOT" "$TARGET_BACKEND_PORT"
sudo nginx -t
sudo systemctl reload nginx
record_active_backend_slot "$TARGET_BACKEND_SLOT"
BACKEND_SWITCH_APPLIED=true
LAST_COMPLETED_STEP="switch backend upstream"
LAST_FAILED_STEP=""
log "step:ok switch backend upstream"

verify_with_retry "stable backend healthz" 30 1 check_backend_healthz_url "$BACKEND_STABLE_BASE_URL"
verify_with_retry "stable backend version" 30 1 check_backend_version_url "$BACKEND_STABLE_BASE_URL"

if [[ "$DEPLOY_MODE" == "full" ]]; then
  if [[ -n "$CURRENT_BEFORE" ]] && ! sudo systemctl is-active --quiet "personal-api-admin-frontend@${CURRENT_FRONTEND_SLOT}"; then
    LAST_FAILED_STEP="bootstrap current frontend slot"
    ensure_frontend_slot_runtime "$CURRENT_FRONTEND_SLOT" "$CURRENT_BEFORE"
    LAST_COMPLETED_STEP="bootstrap current frontend slot"
    LAST_FAILED_STEP=""
    log "step:ok bootstrap current frontend slot"
  fi

  LAST_FAILED_STEP="prepare target frontend slot"
  release_meta_json_set "frontend_slot" "$TARGET_FRONTEND_SLOT"
  ensure_frontend_slot_link "$TARGET_FRONTEND_SLOT" "$RELEASE_DIR"
  LAST_COMPLETED_STEP="prepare target frontend slot"
  LAST_FAILED_STEP=""
  log "step:ok prepare target frontend slot"

  LAST_FAILED_STEP="restart target frontend slot"
  sudo systemctl restart "personal-api-admin-frontend@${TARGET_FRONTEND_SLOT}"
  LAST_COMPLETED_STEP="restart target frontend slot"
  LAST_FAILED_STEP=""
  log "step:ok restart target frontend slot"

  verify_with_retry "target frontend login" 30 1 check_frontend_login_url "http://127.0.0.1:${TARGET_FRONTEND_PORT}"
  verify_with_retry "target frontend version" 30 1 check_frontend_runtime_version_url "http://127.0.0.1:${TARGET_FRONTEND_PORT}"

  LAST_FAILED_STEP="switch frontend upstream"
  write_frontend_upstream_conf "$TARGET_FRONTEND_SLOT" "$TARGET_FRONTEND_PORT"
  sudo nginx -t
  sudo systemctl reload nginx
  record_active_frontend_slot "$TARGET_FRONTEND_SLOT"
  FRONTEND_SWITCH_APPLIED=true
  LAST_COMPLETED_STEP="switch frontend upstream"
  LAST_FAILED_STEP=""
  log "step:ok switch frontend upstream"

  verify_with_retry "stable frontend login" 30 1 check_frontend_login_url "$FRONTEND_STABLE_BASE_URL"
  verify_with_retry "stable frontend version" 30 1 check_frontend_runtime_version_url "$FRONTEND_STABLE_BASE_URL"

  ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
  LAST_COMPLETED_STEP="switch current symlink"
  log "step:ok switch current symlink"

  LAST_FAILED_STEP="restart market_api"
  sudo systemctl restart personal-market-api
  LAST_COMPLETED_STEP="restart market_api"
  LAST_FAILED_STEP=""
  log "step:ok restart market_api"

  verify_with_retry "market_api healthz" 30 1 check_market_api_healthz
  run_n8n_verification
else
  ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
  LAST_COMPLETED_STEP="switch current symlink"
  log "step:ok switch current symlink"
fi

LAST_FAILED_STEP="restart managed timers"
restart_managed_timers_if_needed
LAST_COMPLETED_STEP="restart managed timers"
LAST_FAILED_STEP=""

cleanup_old_releases

LAST_COMPLETED_STEP="cleanup old releases"
log "step:ok cleanup old releases"
log "release activated: $RELEASE_ID mode=$DEPLOY_MODE backend_slot=$TARGET_BACKEND_SLOT frontend_slot=${TARGET_FRONTEND_SLOT:-unchanged}"
