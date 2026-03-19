#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_REPO_DIR="${RELEASE_REPO_DIR:-/srv/my-api/repo}"
SERVER_APP_ROOT="${APP_ROOT:-/srv/my-api}"
ALERT_ON_DRIFT=false
TARGET_HOST=""

usage() {
  cat <<'EOF'
Usage: ./scripts/check_release_drift.sh [--alert-on-drift] <ssh-host-alias-or-hostname>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alert-on-drift)
      ALERT_ON_DRIFT=true
      shift
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

REMOTE_STATE="$(ssh "$TARGET_HOST" "APP_ROOT='$SERVER_APP_ROOT' bash '$SERVER_APP_ROOT/current/scripts/check_server_drift.sh' --json")"

DRIFT_REPORT="$(
  python3 - <<'PY' "$LOCAL_HEAD" "$ORIGIN_MAIN" "$REMOTE_STATE"
import json
import sys

local_head = sys.argv[1]
origin_main = sys.argv[2]
remote_state = json.loads(sys.argv[3])

status = remote_state['status']
issues = list(remote_state['issues'])

server_git_sha = remote_state.get('server_git_sha')
server_release_id = remote_state.get('server_release_id')
server_built_at = remote_state.get('server_built_at')

if local_head != origin_main:
    status = 'drift_detected'
    issues.append(f'local_head != origin/main ({local_head[:7]} != {origin_main[:7]})')

if server_git_sha and server_git_sha != origin_main:
    status = 'drift_detected'
    issues.append(
        'server_current != origin/main '
        f"({(server_git_sha or 'unknown')[:7]} != {origin_main[:7]})"
    )

report = {
    'status': status,
    'local_head': local_head,
    'origin_main': origin_main,
    'server_git_sha': server_git_sha,
    'server_release_id': server_release_id,
    'server_built_at': server_built_at,
    'server_current_release_path': remote_state.get('server_current_release_path'),
    'server_version_error': remote_state.get('server_version_error'),
    'backend_stable_base_url': remote_state.get('backend_stable_base_url'),
    'backend_active_slot': remote_state.get('backend_active_slot'),
    'backend_active_slot_port': remote_state.get('backend_active_slot_port'),
    'backend_release_slot': remote_state.get('backend_release_slot'),
    'backend_version_slot': remote_state.get('backend_version_slot'),
    'backend_upstream_target': remote_state.get('backend_upstream_target'),
    'n8n_compose_path': remote_state.get('n8n_compose_path'),
    'n8n_compose_sha256': remote_state.get('n8n_compose_sha256'),
    'n8n_compose_modified_at': remote_state.get('n8n_compose_modified_at'),
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
print(f"backend_stable_base_url: {report['backend_stable_base_url']}")
print(f"backend_active_slot: {report['backend_active_slot']}")
print(f"backend_active_slot_port: {report['backend_active_slot_port']}")
print(f"backend_release_slot: {report['backend_release_slot']}")
print(f"backend_version_slot: {report['backend_version_slot']}")
print(f"backend_upstream_target: {report['backend_upstream_target']}")
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
