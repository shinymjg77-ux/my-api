#!/usr/bin/env bash

set -euo pipefail

HOST="${N8N_CHECK_HOST:-ansan-jarvis.duckdns.org}"
CONTAINER="${N8N_CONTAINER_NAME:-n8n}"
SECRET="${JOB_SHARED_SECRET:-${1:-}}"

if [[ -z "$SECRET" ]]; then
  echo "Usage: JOB_SHARED_SECRET=<secret> $0 [secret]" >&2
  exit 1
fi

if ! docker ps -a --format '{{.Names}}' | grep -Fx "$CONTAINER" >/dev/null 2>&1; then
  echo "n8n container not found: $CONTAINER" >&2
  exit 10
fi

echo "[1/3] n8n resolv.conf"
docker exec "$CONTAINER" sh -lc 'cat /etc/resolv.conf'

echo
echo "[2/3] DNS lookup from n8n"
if ! docker exec "$CONTAINER" node -e "require('dns').lookup('$HOST', (error, address, family) => { if (error) { console.error(error.message); process.exit(1); } console.log(address, family); })"; then
  exit 20
fi

echo
echo "[3/3] HTTPS ops-check from n8n"
if ! docker exec "$CONTAINER" node -e "(async()=>{try{const r=await fetch('https://$HOST/api/proxy/jobs/ops-check',{headers:{'X-Job-Secret':'$SECRET'}});console.log(r.status, await r.text()); if(!r.ok){process.exitCode=1}}catch(e){console.log(e.message);process.exitCode=1}})()"; then
  exit 21
fi
