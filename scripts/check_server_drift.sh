#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPS_ENV="${OPS_ENV:-/etc/my-api/ops.env}"
APP_ROOT="${APP_ROOT:-/srv/my-api}"
REPO_DIR="${RELEASE_REPO_DIR:-$REPO_ROOT}"
N8N_COMPOSE_PATH="${N8N_COMPOSE_PATH:-/opt/n8n/docker-compose.yml}"
BACKEND_STABLE_BASE_URL="${BACKEND_STABLE_BASE_URL:-http://127.0.0.1:9000}"
BACKEND_UPSTREAM_CONF="${BACKEND_UPSTREAM_CONF:-/etc/nginx/snippets/my-api-backend-upstream.conf}"
BACKEND_ACTIVE_SLOT_STATE_PATH="${BACKEND_ACTIVE_SLOT_STATE_PATH:-$APP_ROOT/state/backend-active-slot}"
BACKEND_SLOT_ENV_DIR="${BACKEND_SLOT_ENV_DIR:-/etc/my-api/backend-slots}"
FRONTEND_STABLE_BASE_URL="${FRONTEND_STABLE_BASE_URL:-http://127.0.0.1:3100}"
FRONTEND_UPSTREAM_CONF="${FRONTEND_UPSTREAM_CONF:-/etc/nginx/snippets/my-api-frontend-upstream.conf}"
FRONTEND_ACTIVE_SLOT_STATE_PATH="${FRONTEND_ACTIVE_SLOT_STATE_PATH:-$APP_ROOT/state/frontend-active-slot}"
FRONTEND_SLOT_ENV_DIR="${FRONTEND_SLOT_ENV_DIR:-/etc/my-api/frontend-slots}"
ALERT_ON_DRIFT=false
JSON_OUTPUT=false

if [[ -r "$OPS_ENV" ]]; then
  set -a
  . "$OPS_ENV"
  set +a
  REPO_DIR="${RELEASE_REPO_DIR:-$REPO_DIR}"
  N8N_COMPOSE_PATH="${N8N_COMPOSE_PATH:-$N8N_COMPOSE_PATH}"
  BACKEND_STABLE_BASE_URL="${BACKEND_STABLE_BASE_URL:-$BACKEND_STABLE_BASE_URL}"
  BACKEND_UPSTREAM_CONF="${BACKEND_UPSTREAM_CONF:-$BACKEND_UPSTREAM_CONF}"
  BACKEND_ACTIVE_SLOT_STATE_PATH="${BACKEND_ACTIVE_SLOT_STATE_PATH:-$BACKEND_ACTIVE_SLOT_STATE_PATH}"
  BACKEND_SLOT_ENV_DIR="${BACKEND_SLOT_ENV_DIR:-$BACKEND_SLOT_ENV_DIR}"
  FRONTEND_STABLE_BASE_URL="${FRONTEND_STABLE_BASE_URL:-$FRONTEND_STABLE_BASE_URL}"
  FRONTEND_UPSTREAM_CONF="${FRONTEND_UPSTREAM_CONF:-$FRONTEND_UPSTREAM_CONF}"
  FRONTEND_ACTIVE_SLOT_STATE_PATH="${FRONTEND_ACTIVE_SLOT_STATE_PATH:-$FRONTEND_ACTIVE_SLOT_STATE_PATH}"
  FRONTEND_SLOT_ENV_DIR="${FRONTEND_SLOT_ENV_DIR:-$FRONTEND_SLOT_ENV_DIR}"
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

SERVER_REPORT="$(APP_ROOT="$APP_ROOT" REPO_DIR="$REPO_DIR" N8N_COMPOSE_PATH="$N8N_COMPOSE_PATH" BACKEND_STABLE_BASE_URL="$BACKEND_STABLE_BASE_URL" BACKEND_UPSTREAM_CONF="$BACKEND_UPSTREAM_CONF" BACKEND_ACTIVE_SLOT_STATE_PATH="$BACKEND_ACTIVE_SLOT_STATE_PATH" BACKEND_SLOT_ENV_DIR="$BACKEND_SLOT_ENV_DIR" FRONTEND_STABLE_BASE_URL="$FRONTEND_STABLE_BASE_URL" FRONTEND_UPSTREAM_CONF="$FRONTEND_UPSTREAM_CONF" FRONTEND_ACTIVE_SLOT_STATE_PATH="$FRONTEND_ACTIVE_SLOT_STATE_PATH" FRONTEND_SLOT_ENV_DIR="$FRONTEND_SLOT_ENV_DIR" python3 - <<'PY'
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess

app_root = pathlib.Path(os.environ["APP_ROOT"])
repo_dir = pathlib.Path(os.environ["REPO_DIR"])
n8n_compose_path = pathlib.Path(os.environ["N8N_COMPOSE_PATH"])
backend_stable_base_url = os.environ["BACKEND_STABLE_BASE_URL"].rstrip("/")
backend_upstream_conf = pathlib.Path(os.environ["BACKEND_UPSTREAM_CONF"])
backend_active_slot_state_path = pathlib.Path(os.environ["BACKEND_ACTIVE_SLOT_STATE_PATH"])
backend_slot_env_dir = pathlib.Path(os.environ["BACKEND_SLOT_ENV_DIR"])
frontend_stable_base_url = os.environ["FRONTEND_STABLE_BASE_URL"].rstrip("/")
frontend_upstream_conf = pathlib.Path(os.environ["FRONTEND_UPSTREAM_CONF"])
frontend_active_slot_state_path = pathlib.Path(os.environ["FRONTEND_ACTIVE_SLOT_STATE_PATH"])
frontend_slot_env_dir = pathlib.Path(os.environ["FRONTEND_SLOT_ENV_DIR"])
current_link = app_root / "current"

current_release_path = None
current_meta = None
current_meta_error = None
version = None
version_error = None
issues: list[str] = []
active_slot = None
active_slot_error = None
upstream_target = None
upstream_error = None
active_slot_port = None
frontend_version = None
frontend_version_error = None
frontend_active_slot = None
frontend_active_slot_error = None
frontend_upstream_target = None
frontend_upstream_error = None
frontend_active_slot_port = None

def read_slot_port(slot: str | None) -> str | None:
    if not slot:
        return None
    path = backend_slot_env_dir / f"{slot}.env"
    if not path.is_file():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "BACKEND_SLOT_PORT" and value.strip():
            return value.strip()
    return None

def read_frontend_slot_port(slot: str | None) -> str | None:
    if not slot:
        return None
    path = frontend_slot_env_dir / f"{slot}.env"
    if not path.is_file():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "FRONTEND_SLOT_PORT" and value.strip():
            return value.strip()
    return None

try:
    current_release_path = current_link.resolve(strict=True)
except FileNotFoundError:
    current_meta_error = "current_release_missing"

if current_release_path is not None:
    meta_path = current_release_path / ".release-meta.json"
    if meta_path.is_file():
        try:
            current_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current_meta_error = "invalid_release_meta"
    else:
        current_meta_error = "missing_release_meta"

if backend_active_slot_state_path.is_file():
    slot = backend_active_slot_state_path.read_text(encoding="utf-8").strip()
    if slot in {"blue", "green"}:
        active_slot = slot
    else:
        active_slot_error = "invalid_active_slot_state"
else:
    active_slot_error = "missing_active_slot_state"

active_slot_port = read_slot_port(active_slot)
if active_slot and not active_slot_port:
    issues.append(f"missing backend slot port for active slot {active_slot}")

if backend_upstream_conf.is_file():
    content = backend_upstream_conf.read_text(encoding="utf-8")
    match = re.search(r"set\s+\$my_api_backend\s+(http://127\.0\.0\.1:\d+);", content)
    if match:
        upstream_target = match.group(1)
    else:
        upstream_error = "invalid_backend_upstream_conf"
else:
    upstream_error = "missing_backend_upstream_conf"

if frontend_active_slot_state_path.is_file():
    slot = frontend_active_slot_state_path.read_text(encoding="utf-8").strip()
    if slot in {"blue", "green"}:
        frontend_active_slot = slot
    else:
        frontend_active_slot_error = "invalid_frontend_active_slot_state"

frontend_active_slot_port = read_frontend_slot_port(frontend_active_slot)
if frontend_active_slot and not frontend_active_slot_port:
    issues.append(f"missing frontend slot port for active slot {frontend_active_slot}")

if frontend_upstream_conf.is_file():
    content = frontend_upstream_conf.read_text(encoding="utf-8")
    match = re.search(r"set\s+\$my_api_frontend\s+(http://127\.0\.0\.1:\d+);", content)
    if match:
        frontend_upstream_target = match.group(1)
    else:
        frontend_upstream_error = "invalid_frontend_upstream_conf"
else:
    frontend_upstream_error = "missing_frontend_upstream_conf"

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
            ["curl", "-fsS", f"{backend_stable_base_url}/version"],
            text=True,
        )
    )
except Exception as exc:
    version_error = str(exc)

try:
    frontend_version = json.loads(
        subprocess.check_output(
            ["curl", "-fsS", f"{frontend_stable_base_url}/api/runtime/version"],
            text=True,
        )
    )
except Exception as exc:
    frontend_version_error = str(exc)

n8n_present = n8n_compose_path.is_file()
n8n_sha256 = None
n8n_modified_at = None
if n8n_present:
    payload = n8n_compose_path.read_bytes()
    stat = n8n_compose_path.stat()
    n8n_sha256 = hashlib.sha256(payload).hexdigest()
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
    release_n8n_compose_sha256 = current_meta.get("n8n_compose_sha256")
    release_backend_slot = current_meta.get("backend_slot")
    release_frontend_slot = current_meta.get("frontend_slot")

    if origin_main and release_git_sha != origin_main:
        status = "drift_detected"
        issues.append(f"server_current != origin/main ({release_git_sha} != {origin_main})")

    if current_release_path and current_release_path.name != release_id:
        status = "drift_detected"
        issues.append(
            f"current symlink release mismatch ({current_release_path.name} != {release_id})"
        )

    if active_slot_error:
        status = "unknown"
        issues.append(active_slot_error)
    elif release_backend_slot and active_slot and release_backend_slot != active_slot:
        status = "drift_detected"
        issues.append(
            f"release backend_slot mismatch ({release_backend_slot} != {active_slot})"
        )

    if upstream_error:
        status = "unknown"
        issues.append(upstream_error)
    elif active_slot_port and upstream_target != f"http://127.0.0.1:{active_slot_port}":
        status = "drift_detected"
        issues.append(
            f"backend upstream mismatch ({upstream_target} != http://127.0.0.1:{active_slot_port})"
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
        if active_slot and version.get("backend_slot") != active_slot:
            status = "drift_detected"
            issues.append(
                f"/version backend_slot mismatch ({version.get('backend_slot')} != {active_slot})"
            )

    if release_frontend_slot:
        if frontend_active_slot_error:
            status = "unknown"
            issues.append(frontend_active_slot_error)
        elif frontend_active_slot != release_frontend_slot:
            status = "drift_detected"
            issues.append(
                f"release frontend_slot mismatch ({release_frontend_slot} != {frontend_active_slot})"
            )

        if frontend_upstream_error:
            status = "unknown"
            issues.append(frontend_upstream_error)
        elif frontend_active_slot_port and frontend_upstream_target != f"http://127.0.0.1:{frontend_active_slot_port}":
            status = "drift_detected"
            issues.append(
                "frontend upstream mismatch "
                f"({frontend_upstream_target} != http://127.0.0.1:{frontend_active_slot_port})"
            )

        if frontend_version is None:
            status = "unknown"
            if frontend_version_error:
                issues.append(f"/api/runtime/version unavailable: {frontend_version_error}")
        else:
            if frontend_version.get("status") != "ok":
                status = "unknown"
                issues.append(f"/api/runtime/version status is {frontend_version.get('status')}")
            if frontend_version.get("git_sha") != release_git_sha:
                status = "drift_detected"
                issues.append(
                    f"/api/runtime/version git_sha mismatch ({frontend_version.get('git_sha')} != {release_git_sha})"
                )
            if frontend_version.get("release_id") != release_id:
                status = "drift_detected"
                issues.append(
                    f"/api/runtime/version release_id mismatch ({frontend_version.get('release_id')} != {release_id})"
                )
            if frontend_active_slot and frontend_version.get("frontend_slot") != frontend_active_slot:
                status = "drift_detected"
                issues.append(
                    "/api/runtime/version frontend_slot mismatch "
                    f"({frontend_version.get('frontend_slot')} != {frontend_active_slot})"
                )

    if n8n_present and release_n8n_compose_sha256:
        if n8n_sha256 != release_n8n_compose_sha256:
            status = "drift_detected"
            issues.append(
                "n8n compose hash mismatch "
                f"({n8n_sha256} != {release_n8n_compose_sha256})"
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
    "backend_stable_base_url": backend_stable_base_url,
    "backend_active_slot": active_slot,
    "backend_active_slot_port": active_slot_port,
    "backend_release_slot": current_meta.get("backend_slot") if current_meta else None,
    "backend_version_slot": version.get("backend_slot") if isinstance(version, dict) else None,
    "backend_upstream_target": upstream_target,
    "frontend_stable_base_url": frontend_stable_base_url,
    "frontend_active_slot": frontend_active_slot,
    "frontend_active_slot_port": frontend_active_slot_port,
    "frontend_release_slot": current_meta.get("frontend_slot") if current_meta else None,
    "frontend_version_slot": frontend_version.get("frontend_slot") if isinstance(frontend_version, dict) else None,
    "frontend_upstream_target": frontend_upstream_target,
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
print(f"backend_stable_base_url: {report['backend_stable_base_url']}")
print(f"backend_active_slot: {report['backend_active_slot']}")
print(f"backend_active_slot_port: {report['backend_active_slot_port']}")
print(f"backend_release_slot: {report['backend_release_slot']}")
print(f"backend_version_slot: {report['backend_version_slot']}")
print(f"backend_upstream_target: {report['backend_upstream_target']}")
print(f"frontend_stable_base_url: {report['frontend_stable_base_url']}")
print(f"frontend_active_slot: {report['frontend_active_slot']}")
print(f"frontend_active_slot_port: {report['frontend_active_slot_port']}")
print(f"frontend_release_slot: {report['frontend_release_slot']}")
print(f"frontend_version_slot: {report['frontend_version_slot']}")
print(f"frontend_upstream_target: {report['frontend_upstream_target']}")
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
  if grep -q 'n8n compose hash mismatch' <<<"$SERVER_REPORT"; then
    ALERT_TITLE="n8n config drift detected"
  elif grep -q 'missing_release_meta\|invalid_release_meta\|missing_active_slot_state\|invalid_backend_upstream_conf\|/version unavailable' <<<"$SERVER_REPORT"; then
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
    f"backend_active_slot={report['backend_active_slot']}",
    f"backend_upstream_target={report['backend_upstream_target']}",
    f"frontend_active_slot={report['frontend_active_slot']}",
    f"frontend_upstream_target={report['frontend_upstream_target']}",
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
