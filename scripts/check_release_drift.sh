#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_ROOT="${APP_ROOT:-/srv/my-api}"
N8N_COMPOSE_PATH="${N8N_COMPOSE_PATH:-/opt/n8n/docker-compose.yml}"
ALERT_ON_DRIFT=false
TARGET_HOST=""

usage() {
  cat <<'EOF'
Usage: ./scripts/check_release_drift.sh [--alert-on-drift] [--n8n-compose-path PATH] <ssh-host-alias-or-hostname>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alert-on-drift)
      ALERT_ON_DRIFT=true
      shift
      ;;
    --n8n-compose-path)
      N8N_COMPOSE_PATH="${2:?missing path for --n8n-compose-path}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$TARGET_HOST" ]]; then
        usage >&2
        exit 1
      fi
      TARGET_HOST="$1"
      shift
      ;;
  esac
done

if [[ -z "$TARGET_HOST" ]]; then
  usage >&2
  exit 1
fi

git -C "$REPO_ROOT" fetch origin main --quiet

LOCAL_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD)"
ORIGIN_MAIN="$(git -C "$REPO_ROOT" rev-parse origin/main)"

REMOTE_STATE="$(
  ssh "$TARGET_HOST" "APP_ROOT='$APP_ROOT' N8N_COMPOSE_PATH='$N8N_COMPOSE_PATH' python3 - <<'PY'
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess

app_root = pathlib.Path(os.environ['APP_ROOT'])
n8n_path = pathlib.Path(os.environ['N8N_COMPOSE_PATH'])
result = {
    'server': {
        'version': None,
        'version_error': None,
        'current_release_path': None,
    },
    'n8n': {
        'path': str(n8n_path),
        'present': False,
        'sha256': None,
        'modified_at': None,
        'modified_at_epoch': None,
    },
}

try:
    result['server']['current_release_path'] = subprocess.check_output(
        ['readlink', '-f', str(app_root / 'current')],
        text=True,
    ).strip()
except Exception:
    result['server']['current_release_path'] = None

try:
    version_raw = subprocess.check_output(
        ['curl', '-fsS', 'http://127.0.0.1:8000/version'],
        text=True,
    )
    result['server']['version'] = json.loads(version_raw)
except Exception as exc:
    result['server']['version_error'] = str(exc)

if n8n_path.is_file():
    payload = n8n_path.read_bytes()
    stat = n8n_path.stat()
    result['n8n']['present'] = True
    result['n8n']['sha256'] = hashlib.sha256(payload).hexdigest()
    result['n8n']['modified_at_epoch'] = int(stat.st_mtime)
    result['n8n']['modified_at'] = dt.datetime.fromtimestamp(
        stat.st_mtime,
        dt.timezone.utc,
    ).strftime('%Y-%m-%dT%H:%M:%SZ')

print(json.dumps(result))
PY"
)"

DRIFT_REPORT="$(
  python3 - <<'PY' "$LOCAL_HEAD" "$ORIGIN_MAIN" "$REMOTE_STATE"
import datetime as dt
import json
import sys

local_head = sys.argv[1]
origin_main = sys.argv[2]
remote_state = json.loads(sys.argv[3])

status = 'in_sync'
issues = []

server_version = remote_state['server'].get('version') or {}
server_git_sha = server_version.get('git_sha')
server_release_id = server_version.get('release_id')
server_built_at = server_version.get('built_at')
server_status = server_version.get('status')

if local_head != origin_main:
    status = 'drift_detected'
    issues.append(f'local_head != origin/main ({local_head[:7]} != {origin_main[:7]})')

if server_git_sha != origin_main:
    status = 'drift_detected'
    issues.append(
        'server_current != origin/main '
        f"({(server_git_sha or 'unknown')[:7]} != {origin_main[:7]})"
    )

if server_status != 'ok':
    status = 'unknown'
    issues.append(f"server /version status is {server_status or 'unavailable'}")

n8n_state = remote_state['n8n']
if n8n_state.get('present') and server_built_at:
    built_at = dt.datetime.fromisoformat(server_built_at.replace('Z', '+00:00'))
    modified_at = dt.datetime.fromtimestamp(
        n8n_state['modified_at_epoch'],
        dt.timezone.utc,
    )
    if modified_at > built_at:
        status = 'drift_detected'
        issues.append(
            'n8n compose changed after app release '
            f"({n8n_state['modified_at']} > {server_built_at})"
        )
elif not n8n_state.get('present'):
    if status == 'in_sync':
        status = 'unknown'
    issues.append('n8n compose file is missing')

report = {
    'status': status,
    'local_head': local_head,
    'origin_main': origin_main,
    'server_git_sha': server_git_sha,
    'server_release_id': server_release_id,
    'server_built_at': server_built_at,
    'server_current_release_path': remote_state['server'].get('current_release_path'),
    'server_version_error': remote_state['server'].get('version_error'),
    'n8n_compose_path': n8n_state.get('path'),
    'n8n_compose_sha256': n8n_state.get('sha256'),
    'n8n_compose_modified_at': n8n_state.get('modified_at'),
    'issues': issues,
}

print(json.dumps(report))
PY
)"

python3 - <<'PY' "$DRIFT_REPORT"
import json
import sys

report = json.loads(sys.argv[1])

print(f"status: {report['status']}")
print(f"local_head: {report['local_head']}")
print(f"origin_main: {report['origin_main']}")
print(f"server_git_sha: {report['server_git_sha']}")
print(f"server_release_id: {report['server_release_id']}")
print(f"server_built_at: {report['server_built_at']}")
print(f"server_current_release_path: {report['server_current_release_path']}")
print(f"n8n_compose_path: {report['n8n_compose_path']}")
print(f"n8n_compose_sha256: {report['n8n_compose_sha256']}")
print(f"n8n_compose_modified_at: {report['n8n_compose_modified_at']}")

if report['server_version_error']:
    print(f"server_version_error: {report['server_version_error']}")

if report['issues']:
    print('issues:')
    for issue in report['issues']:
        print(f"- {issue}")
PY

DRIFT_STATUS="$(python3 - <<'PY' "$DRIFT_REPORT"
import json
import sys
print(json.loads(sys.argv[1])['status'])
PY
)"

if [[ "$ALERT_ON_DRIFT" == "true" && "$DRIFT_STATUS" == "drift_detected" ]]; then
  "$SCRIPT_DIR/send_alert.sh" "Version drift detected" "$(python3 - <<'PY' "$DRIFT_REPORT"
import json
import sys

report = json.loads(sys.argv[1])
lines = [
    f"local_head={report['local_head']}",
    f"origin_main={report['origin_main']}",
    f"server_git_sha={report['server_git_sha']}",
    f"server_release_id={report['server_release_id']}",
]
lines.extend(f"issue={issue}" for issue in report['issues'])
print('\n'.join(lines))
PY
)"
fi

if [[ "$DRIFT_STATUS" == "drift_detected" ]]; then
  exit 2
fi

if [[ "$DRIFT_STATUS" == "unknown" ]]; then
  exit 3
fi
