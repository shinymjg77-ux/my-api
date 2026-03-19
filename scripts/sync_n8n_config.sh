#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"
OPS_ENV="${OPS_ENV:-/etc/my-api/ops.env}"
N8N_PROJECT_DIR="${N8N_PROJECT_DIR:-/opt/n8n}"
N8N_COMPOSE_PATH="${N8N_COMPOSE_PATH:-$N8N_PROJECT_DIR/docker-compose.yml}"
N8N_ENV_FILE="${N8N_ENV_FILE:-/etc/my-api/n8n.env}"
N8N_CONTAINER_NAME="${N8N_CONTAINER_NAME:-n8n}"
SOURCE_COMPOSE="$RELEASE_DIR/deploy/docker/n8n.compose.prod.yml"

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
}

if [[ -r "$OPS_ENV" ]]; then
  set -a
  . "$OPS_ENV"
  set +a
  N8N_PROJECT_DIR="${N8N_PROJECT_DIR:-$N8N_PROJECT_DIR}"
  N8N_COMPOSE_PATH="${N8N_COMPOSE_PATH:-$N8N_COMPOSE_PATH}"
  N8N_ENV_FILE="${N8N_ENV_FILE:-$N8N_ENV_FILE}"
  N8N_CONTAINER_NAME="${N8N_CONTAINER_NAME:-$N8N_CONTAINER_NAME}"
fi

if [[ ! -f "$SOURCE_COMPOSE" ]]; then
  echo "n8n source compose not found: $SOURCE_COMPOSE" >&2
  exit 1
fi

if [[ ! -f "$N8N_ENV_FILE" ]]; then
  echo "n8n env file not found: $N8N_ENV_FILE" >&2
  exit 1
fi

sudo install -d -m 755 "$N8N_PROJECT_DIR"
sudo docker compose --env-file "$N8N_ENV_FILE" -f "$SOURCE_COMPOSE" config >/dev/null

SOURCE_HASH="$(sha256_file "$SOURCE_COMPOSE")"
CURRENT_HASH=""

if sudo test -f "$N8N_COMPOSE_PATH"; then
  CURRENT_HASH="$(sudo python3 - <<'PY' "$N8N_COMPOSE_PATH"
import hashlib
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
)"
fi

NEEDS_APPLY=false
if [[ "$SOURCE_HASH" != "$CURRENT_HASH" ]]; then
  NEEDS_APPLY=true
  sudo install -m 644 "$SOURCE_COMPOSE" "$N8N_COMPOSE_PATH"
fi

if ! sudo docker ps -a --format '{{.Names}}' | grep -Fx "$N8N_CONTAINER_NAME" >/dev/null 2>&1; then
  NEEDS_APPLY=true
fi

if [[ "$NEEDS_APPLY" == "true" ]]; then
  sudo docker compose --env-file "$N8N_ENV_FILE" -f "$N8N_COMPOSE_PATH" up -d
fi

DNS_JSON="$(sudo docker inspect "$N8N_CONTAINER_NAME" --format '{{json .HostConfig.Dns}}')"
if [[ "$DNS_JSON" == "null" || "$DNS_JSON" == "[]" ]]; then
  echo "n8n container DNS is not configured" >&2
  exit 1
fi

ENV_LINES="$(sudo docker inspect "$N8N_CONTAINER_NAME" --format '{{range .Config.Env}}{{println .}}{{end}}')"
for required_prefix in "N8N_PORT=" "N8N_PROTOCOL=" "N8N_EDITOR_BASE_URL="; do
  if ! grep -q "^${required_prefix}" <<<"$ENV_LINES"; then
    echo "n8n container missing env: $required_prefix" >&2
    exit 1
  fi
done

if [[ "$NEEDS_APPLY" == "true" ]]; then
  echo "[n8n-sync] applied compose config at $N8N_COMPOSE_PATH"
else
  echo "[n8n-sync] compose config already in sync"
fi
