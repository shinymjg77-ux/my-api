#!/usr/bin/env bash
set -euo pipefail

OPS_ENV="${OPS_ENV:-/etc/my-api/ops.env}"
TITLE="${1:-My API alert}"
BODY="${2:-}"

if [[ -r "$OPS_ENV" ]]; then
  set -a
  . "$OPS_ENV"
  set +a
fi

if [[ -z "${ALERT_WEBHOOK_URL:-}" ]]; then
  exit 0
fi

timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
source_name="${ALERT_SOURCE:-my-api}"
payload_text="[$source_name] $TITLE"$'\n'"$BODY"$'\n'"$timestamp"
webhook_type="${ALERT_WEBHOOK_TYPE:-discord}"

case "$webhook_type" in
  slack)
    /usr/bin/curl -fsS -X POST "$ALERT_WEBHOOK_URL" \
      -H "content-type: application/json" \
      -d "$(python3 - <<'PY' "$payload_text"
import json
import sys
print(json.dumps({"text": sys.argv[1]}))
PY
)"
    ;;
  generic)
    /usr/bin/curl -fsS -X POST "$ALERT_WEBHOOK_URL" \
      -H "content-type: application/json" \
      -d "$(python3 - <<'PY' "$TITLE" "$BODY" "$source_name" "$timestamp"
import json
import sys
print(json.dumps({
    "title": sys.argv[1],
    "body": sys.argv[2],
    "source": sys.argv[3],
    "timestamp": sys.argv[4],
}))
PY
)"
    ;;
  *)
    /usr/bin/curl -fsS -X POST "$ALERT_WEBHOOK_URL" \
      -H "content-type: application/json" \
      -d "$(python3 - <<'PY' "$payload_text"
import json
import sys
print(json.dumps({"content": sys.argv[1]}))
PY
)"
    ;;
esac
