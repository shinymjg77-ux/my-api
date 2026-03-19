#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPS_ENV="${OPS_ENV:-/etc/my-api/ops.env}"
APP_ROOT="${APP_ROOT:-/srv/my-api}"
REPO_DIR="${RELEASE_REPO_DIR:-$REPO_ROOT}"
N8N_COMPOSE_PATH="${N8N_COMPOSE_PATH:-/opt/n8n/docker-compose.yml}"
ALERT_ON_DRIFT=false
JSON_OUTPUT=false

if [[ -r "$OPS_ENV" ]]; then
  set -a
  . "$OPS_ENV"
  set +a
  REPO_DIR="${RELEASE_REPO_DIR:-$REPO_DIR}"
  N8N_COMPOSE_PATH="${N8N_COMPOSE_PATH:-$N8N_COMPOSE_PATH}"
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alert-on-drift)
      ALERT_ON_DRIFT=true
      shift
      ;;
    --json)
      JSON_OUTPUT=true
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/check_server_drift.sh [--json] [--alert-on-drift]
EOF
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 1
      ;;
  esac
done

SERVER_REPORT="$(APP_ROOT="$APP_ROOT" REPO_DIR="$REPO_DIR" N8N_COMPOSE_PATH="$N8N_COMPOSE_PATH" python3 - <<'PY'
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess

app_root = pathlib.Path(os.environ["APP_ROOT"])
repo_dir = pathlib.Path(os.environ["REPO_DIR"])
n8n_compose_path = pathlib.Path(os.environ["N8N_COMPOSE_PATH"])
current_link = app_root / "current"
current_release_path = None
current_meta_path = None
current_meta = None
current_meta_error = None
version = None
version_error = None
issues: list[str] = []

try:
    current_release_path = current_link.resolve(strict=True)
except FileNotFoundError:
    current_release_path = None
    current_meta_error = "current_release_missing"

if current_release_path is not None:
    current_meta_path = current_release_path / ".release-meta.json"
    if current_meta_path.is_file():
        try:
            current_meta = json.loads(current_meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current_meta_error = "invalid_release_meta"
    else:
        current_meta_error = "missing_release_meta"

try:
    subprocess.check_output(
        ["git", "-C", str(repo_dir), "fetch", "origin", "main", "--quiet"],
        text=True,
    )
    origin_main = subprocess.check_output(
        ["git", "-C", str(repo_dir), "rev-parse", "origin/main"],
        text=True,
    ).strip()
except Exception as exc:
    origin_main = None
    issues.append(f"repo fetch failed: {exc}")

try:
    version = json.loads(
        subprocess.check_output(
            ["curl", "-fsS", "http://127.0.0.1:8000/version"],
            text=True,
        )
    )
except Exception as exc:
    version_error = str(exc)

n8n_present = n8n_compose_path.is_file()
n8n_sha256 = None
n8n_modified_at = None
n8n_modified_at_epoch = None
if n8n_present:
    payload = n8n_compose_path.read_bytes()
    stat = n8n_compose_path.stat()
    n8n_sha256 = hashlib.sha256(payload).hexdigest()
    n8n_modified_at_epoch = int(stat.st_mtime)
    n8n_modified_at = dt.datetime.fromtimestamp(
        stat.st_mtime,
        dt.timezone.utc,
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

status = "in_sync"

if origin_main is None:
    status = "unknown"

if current_meta is None:
    status = "unknown"
    if current_meta_error:
        issues.append(current_meta_error)
else:
    release_git_sha = current_meta.get("git_sha")
    release_id = current_meta.get("release_id")
    built_at = current_meta.get("built_at")

    if origin_main and release_git_sha != origin_main:
        status = "drift_detected"
        issues.append(f"server_current != origin/main ({release_git_sha} != {origin_main})")

    if current_release_path and current_release_path.name != release_id:
        status = "drift_detected"
        issues.append(
            f"current symlink release mismatch ({current_release_path.name} != {release_id})"
        )

    if version is None:
        status = "unknown"
        if version_error:
            issues.append(f"/version unavailable: {version_error}")
    else:
        if version.get("status") != "ok":
            status = "unknown"
            issues.append(f"/version status is {version.get('status')}")
        if version.get("git_sha") != release_git_sha:
            status = "drift_detected"
            issues.append(
                f"/version git_sha mismatch ({version.get('git_sha')} != {release_git_sha})"
            )
        if version.get("release_id") != release_id:
            status = "drift_detected"
            issues.append(
                f"/version release_id mismatch ({version.get('release_id')} != {release_id})"
            )

    if n8n_present and built_at:
        built_at_dt = dt.datetime.fromisoformat(built_at.replace("Z", "+00:00"))
        modified_at_dt = dt.datetime.fromtimestamp(n8n_modified_at_epoch, dt.timezone.utc)
        if modified_at_dt > built_at_dt:
            status = "drift_detected"
            issues.append(
                f"n8n compose changed after app release ({n8n_modified_at} > {built_at})"
            )
    elif not n8n_present:
        if status == "in_sync":
            status = "unknown"
        issues.append("n8n compose file is missing")

report = {
    "status": status,
    "origin_main": origin_main,
    "server_git_sha": current_meta.get("git_sha") if current_meta else None,
    "server_release_id": current_meta.get("release_id") if current_meta else None,
    "server_built_at": current_meta.get("built_at") if current_meta else None,
    "server_current_release_path": str(current_release_path) if current_release_path else None,
    "server_version_error": version_error,
    "n8n_compose_path": str(n8n_compose_path),
    "n8n_compose_sha256": n8n_sha256,
    "n8n_compose_modified_at": n8n_modified_at,
    "issues": issues,
}
print(json.dumps(report))
PY
)"

if [[ "$JSON_OUTPUT" == "true" ]]; then
  printf '%s\n' "$SERVER_REPORT"
else
  python3 - <<'PY' "$SERVER_REPORT"
import json
import sys

report = json.loads(sys.argv[1])
print(f"status: {report['status']}")
print(f"origin_main: {report['origin_main']}")
print(f"server_git_sha: {report['server_git_sha']}")
print(f"server_release_id: {report['server_release_id']}")
print(f"server_built_at: {report['server_built_at']}")
print(f"server_current_release_path: {report['server_current_release_path']}")
print(f"n8n_compose_path: {report['n8n_compose_path']}")
print(f"n8n_compose_sha256: {report['n8n_compose_sha256']}")
print(f"n8n_compose_modified_at: {report['n8n_compose_modified_at']}")
if report["server_version_error"]:
    print(f"server_version_error: {report['server_version_error']}")
if report["issues"]:
    print("issues:")
    for issue in report["issues"]:
        print(f"- {issue}")
PY
fi

DRIFT_STATUS="$(python3 - <<'PY' "$SERVER_REPORT"
import json
import sys
print(json.loads(sys.argv[1])["status"])
PY
)"

if [[ "$ALERT_ON_DRIFT" == "true" && "$DRIFT_STATUS" != "in_sync" ]]; then
  ALERT_TITLE="Version drift detected"
  if grep -q 'n8n compose changed after app release' <<<"$SERVER_REPORT"; then
    ALERT_TITLE="n8n config drift detected"
  elif grep -q 'missing_release_meta\|invalid_release_meta\|/version unavailable' <<<"$SERVER_REPORT"; then
    ALERT_TITLE="Server release metadata missing"
  fi
  "$SCRIPT_DIR/send_alert.sh" "$ALERT_TITLE" "$(python3 - <<'PY' "$SERVER_REPORT"
import json
import sys

report = json.loads(sys.argv[1])
lines = [
    f"origin_main={report['origin_main']}",
    f"server_git_sha={report['server_git_sha']}",
    f"server_release_id={report['server_release_id']}",
]
lines.extend(f"issue={issue}" for issue in report["issues"])
print("\n".join(lines))
PY
)"
fi

if [[ "$DRIFT_STATUS" == "drift_detected" ]]; then
  exit 2
fi

if [[ "$DRIFT_STATUS" == "unknown" ]]; then
  exit 3
fi
