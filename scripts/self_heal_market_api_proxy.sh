#!/usr/bin/env bash
set -euo pipefail

OPS_ENV="${OPS_ENV:-/etc/my-api/ops.env}"
MARKET_API_BIND_HOST="${MARKET_API_BIND_HOST:-127.0.0.1}"
MARKET_API_PORT="${MARKET_API_PORT:-8100}"
NGINX_SITE_CONF="${NGINX_SITE_CONF:-/etc/nginx/sites-available/btcore-log-console.conf}"
OPS_PUBLIC_BASE_URL="${OPS_PUBLIC_BASE_URL:-}"

log() {
  echo "[self-heal-market-api-proxy] $*" >&2
}

if [[ -r "$OPS_ENV" ]]; then
  set -a
  . "$OPS_ENV"
  set +a
  MARKET_API_BIND_HOST="${MARKET_API_BIND_HOST:-$MARKET_API_BIND_HOST}"
  MARKET_API_PORT="${MARKET_API_PORT:-$MARKET_API_PORT}"
  NGINX_SITE_CONF="${NGINX_SITE_CONF:-$NGINX_SITE_CONF}"
  OPS_PUBLIC_BASE_URL="${OPS_PUBLIC_BASE_URL:-$OPS_PUBLIC_BASE_URL}"
fi

if [[ -z "$OPS_PUBLIC_BASE_URL" ]]; then
  if [[ -n "${ALERT_SOURCE:-}" ]]; then
    if [[ "$ALERT_SOURCE" == http://* || "$ALERT_SOURCE" == https://* ]]; then
      OPS_PUBLIC_BASE_URL="${ALERT_SOURCE%/}"
    else
      OPS_PUBLIC_BASE_URL="https://${ALERT_SOURCE}"
    fi
  else
    OPS_PUBLIC_BASE_URL="https://ansan-jarvis.duckdns.org"
  fi
fi

LOCAL_HEALTH_URL="http://${MARKET_API_BIND_HOST}:${MARKET_API_PORT}/healthz"
PUBLIC_HEALTH_URL="${OPS_PUBLIC_BASE_URL%/}/internal/market-api/healthz"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fetch_status() {
  local url="$1"
  local body_file="$2"
  curl -sS --max-time 10 -o "$body_file" -w '%{http_code}' "$url" || true
}

if ! curl -fsS --max-time 10 "$LOCAL_HEALTH_URL" | grep -q '"status":"ok"'; then
  log "local market_api health check failed: $LOCAL_HEALTH_URL"
  exit 20
fi

PUBLIC_STATUS="$(fetch_status "$PUBLIC_HEALTH_URL" "$TMP_DIR/public-health.txt")"
if [[ "$PUBLIC_STATUS" == "200" ]] && grep -q '"status":"ok"' "$TMP_DIR/public-health.txt"; then
  log "public market_api route already healthy"
  exit 0
fi

if ! sudo test -r "$NGINX_SITE_CONF"; then
  log "nginx site config is not readable: $NGINX_SITE_CONF"
  exit 22
fi

if sudo grep -q 'location \^~ /internal/market-api/' "$NGINX_SITE_CONF"; then
  log "public route is unhealthy but proxy block already exists (status=$PUBLIC_STATUS)"
  exit 21
fi

log "missing /internal/market-api/ proxy block detected; attempting repair"

sudo python3 - <<'PY' "$NGINX_SITE_CONF" "$MARKET_API_BIND_HOST" "$MARKET_API_PORT"
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

path = Path(sys.argv[1])
host = sys.argv[2]
port = sys.argv[3]

text = path.read_text(encoding="utf-8")
needle = "location ^~ /internal/market-api/"
if needle in text:
    raise SystemExit(0)

block = (
    "    location ^~ /internal/market-api/ {\n"
    f"        proxy_pass http://{host}:{port}/;\n"
    "        proxy_read_timeout 30s;\n"
    "    }\n\n"
)

markers = (
    "    location ^~ /webhook/ {",
    "    location ^~ /webhook-test/ {",
    "    location = /api/auth/login {",
    "    location /_next/static/ {",
    "    location / {",
)

for marker in markers:
    if marker in text:
        backup = path.with_name(
            f"{path.name}.bak-autoheal-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        )
        shutil.copy2(path, backup)
        path.write_text(text.replace(marker, block + marker, 1), encoding="utf-8")
        print(str(backup))
        break
else:
    raise SystemExit("could not find insertion marker in nginx site config")
PY

sudo nginx -t >/dev/null
sudo systemctl reload nginx

PUBLIC_STATUS="$(fetch_status "$PUBLIC_HEALTH_URL" "$TMP_DIR/public-health-after.txt")"
if [[ "$PUBLIC_STATUS" == "200" ]] && grep -q '"status":"ok"' "$TMP_DIR/public-health-after.txt"; then
  log "repaired nginx market_api proxy and verified public health"
  exit 0
fi

log "proxy repair applied but public route is still unhealthy (status=$PUBLIC_STATUS)"
exit 23
