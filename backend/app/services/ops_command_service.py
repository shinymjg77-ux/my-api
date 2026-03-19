import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import HTTPException, status

from .. import schemas
from ..config import PROJECT_ROOT, settings
from ..release_meta import load_release_meta
from .ops_dashboard_service import get_ops_dashboard_overview


OPS_ENV_PATH = Path("/etc/my-api/ops.env")
BACKEND_UPSTREAM_PATTERN = re.compile(r"set\s+\$my_api_backend\s+(http://127\.0\.0\.1:\d+);")
FRONTEND_UPSTREAM_PATTERN = re.compile(r"set\s+\$my_api_frontend\s+(http://127\.0\.0\.1:\d+);")
SUPPORTED_COMMANDS: dict[str, str] = {
    "status.help": "Show supported /ops commands.",
    "status.version": "Show current release id, git SHA, and active slots.",
    "status.drift": "Show current drift status and mismatches.",
    "status.overview": "Show service health summary and active warnings.",
}


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _ops_runtime_config() -> dict[str, str]:
    env_values = _read_env_file(Path(OPS_ENV_PATH))
    app_root = env_values.get("APP_ROOT", "/srv/my-api")

    return {
        "app_root": app_root,
        "release_repo_dir": env_values.get("RELEASE_REPO_DIR", str(PROJECT_ROOT / "repo")),
        "n8n_compose_path": env_values.get("N8N_COMPOSE_PATH", "/opt/n8n/docker-compose.yml"),
        "frontend_stable_base_url": env_values.get("FRONTEND_STABLE_BASE_URL", "http://127.0.0.1:3100").rstrip("/"),
        "backend_active_slot_state_path": env_values.get(
            "BACKEND_ACTIVE_SLOT_STATE_PATH",
            f"{app_root}/state/backend-active-slot",
        ),
        "frontend_active_slot_state_path": env_values.get(
            "FRONTEND_ACTIVE_SLOT_STATE_PATH",
            f"{app_root}/state/frontend-active-slot",
        ),
        "backend_slot_env_dir": env_values.get("BACKEND_SLOT_ENV_DIR", "/etc/my-api/backend-slots"),
        "frontend_slot_env_dir": env_values.get("FRONTEND_SLOT_ENV_DIR", "/etc/my-api/frontend-slots"),
        "backend_upstream_conf": env_values.get(
            "BACKEND_UPSTREAM_CONF",
            "/etc/nginx/snippets/my-api-backend-upstream.conf",
        ),
        "frontend_upstream_conf": env_values.get(
            "FRONTEND_UPSTREAM_CONF",
            "/etc/nginx/snippets/my-api-frontend-upstream.conf",
        ),
    }


def _read_state_value(path: str) -> str | None:
    state_path = Path(path)
    if not state_path.is_file():
        return None
    value = state_path.read_text(encoding="utf-8").strip()
    if value in {"blue", "green"}:
        return value
    return None


def _read_slot_port(slot: str | None, env_dir: str, key: str) -> str | None:
    if not slot:
        return None

    path = Path(env_dir) / f"{slot}.env"
    if not path.is_file():
        return None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        env_key, value = line.split("=", 1)
        if env_key == key and value.strip():
            return value.strip()
    return None


def _read_upstream_target(path: str, pattern: re.Pattern[str]) -> str | None:
    upstream_path = Path(path)
    if not upstream_path.is_file():
        return None

    match = pattern.search(upstream_path.read_text(encoding="utf-8"))
    if not match:
        return None
    return match.group(1)


def _fetch_json(url: str, timeout: float = 5.0) -> tuple[dict | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, str(exc)

    if not isinstance(payload, dict):
        return None, "invalid_json_shape"
    return payload, None


def _git_origin_main(repo_dir: str) -> tuple[str | None, str | None]:
    try:
        subprocess.run(
            ["git", "-C", repo_dir, "fetch", "origin", "main", "--quiet"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        completed = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "origin/main"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)

    return completed.stdout.strip(), None


def _n8n_compose_hash(path: str) -> tuple[str | None, str | None]:
    compose_path = Path(path)
    if not compose_path.is_file():
        return None, "missing_n8n_compose"
    return hashlib.sha256(compose_path.read_bytes()).hexdigest(), None


def _build_version_payload() -> dict[str, object]:
    meta, error = load_release_meta()
    runtime_config = _ops_runtime_config()
    frontend_runtime, frontend_runtime_error = _fetch_json(
        f"{runtime_config['frontend_stable_base_url']}/api/runtime/version"
    )
    backend_active_slot = _read_state_value(runtime_config["backend_active_slot_state_path"])
    frontend_active_slot = _read_state_value(runtime_config["frontend_active_slot_state_path"])

    payload: dict[str, object] = {
        "status": "ok" if meta else "degraded",
        "app_name": settings.app_name,
        "environment": settings.environment,
        "git_sha": meta.get("git_sha") if meta else None,
        "release_id": meta.get("release_id") if meta else None,
        "built_at": meta.get("built_at") if meta else None,
        "backend_slot": meta.get("backend_slot") if meta else None,
        "frontend_slot": meta.get("frontend_slot") if meta else None,
        "backend_active_slot": backend_active_slot,
        "frontend_active_slot": frontend_active_slot,
        "frontend_runtime_status": frontend_runtime.get("status") if frontend_runtime else None,
        "frontend_runtime_error": frontend_runtime_error,
        "missing_release_meta": meta is None,
        "release_meta_error": error,
    }
    return payload


def build_drift_report() -> dict[str, object]:
    runtime_config = _ops_runtime_config()
    current_link = Path(runtime_config["app_root"]) / "current"
    current_meta, current_meta_error = load_release_meta(current_link / ".release-meta.json")
    current_release_path = str(current_link.resolve(strict=False)) if current_link.exists() else None
    origin_main, origin_main_error = _git_origin_main(runtime_config["release_repo_dir"])
    frontend_runtime, frontend_runtime_error = _fetch_json(
        f"{runtime_config['frontend_stable_base_url']}/api/runtime/version"
    )

    backend_active_slot = _read_state_value(runtime_config["backend_active_slot_state_path"])
    frontend_active_slot = _read_state_value(runtime_config["frontend_active_slot_state_path"])
    backend_active_slot_port = _read_slot_port(
        backend_active_slot,
        runtime_config["backend_slot_env_dir"],
        "BACKEND_SLOT_PORT",
    )
    frontend_active_slot_port = _read_slot_port(
        frontend_active_slot,
        runtime_config["frontend_slot_env_dir"],
        "FRONTEND_SLOT_PORT",
    )
    backend_upstream_target = _read_upstream_target(
        runtime_config["backend_upstream_conf"],
        BACKEND_UPSTREAM_PATTERN,
    )
    frontend_upstream_target = _read_upstream_target(
        runtime_config["frontend_upstream_conf"],
        FRONTEND_UPSTREAM_PATTERN,
    )
    n8n_compose_sha256, n8n_compose_error = _n8n_compose_hash(runtime_config["n8n_compose_path"])

    issues: list[str] = []
    status_value: str = "in_sync"

    if origin_main_error:
        status_value = "unknown"
        issues.append(f"repo fetch failed: {origin_main_error}")

    if not current_meta:
        status_value = "unknown"
        issues.append(current_meta_error or "missing_release_meta")
    else:
        release_git_sha = current_meta.get("git_sha")
        release_id = current_meta.get("release_id")
        release_backend_slot = current_meta.get("backend_slot")
        release_frontend_slot = current_meta.get("frontend_slot")
        release_n8n_compose_sha256 = current_meta.get("n8n_compose_sha256")

        if origin_main and release_git_sha != origin_main:
            status_value = "drift_detected"
            issues.append(f"server_current != origin/main ({release_git_sha} != {origin_main})")

        if current_release_path and Path(current_release_path).name != release_id:
            status_value = "drift_detected"
            issues.append(f"current symlink release mismatch ({Path(current_release_path).name} != {release_id})")

        if release_backend_slot and backend_active_slot != release_backend_slot:
            status_value = "drift_detected"
            issues.append(f"release backend_slot mismatch ({release_backend_slot} != {backend_active_slot})")

        if backend_active_slot_port and backend_upstream_target != f"http://127.0.0.1:{backend_active_slot_port}":
            status_value = "drift_detected"
            issues.append(
                f"backend upstream mismatch ({backend_upstream_target} != http://127.0.0.1:{backend_active_slot_port})"
            )

        if release_frontend_slot and frontend_active_slot != release_frontend_slot:
            status_value = "drift_detected"
            issues.append(f"release frontend_slot mismatch ({release_frontend_slot} != {frontend_active_slot})")

        if frontend_active_slot_port and frontend_upstream_target != f"http://127.0.0.1:{frontend_active_slot_port}":
            status_value = "drift_detected"
            issues.append(
                f"frontend upstream mismatch ({frontend_upstream_target} != http://127.0.0.1:{frontend_active_slot_port})"
            )

        if frontend_runtime is None:
            status_value = "unknown"
            issues.append(f"/api/runtime/version unavailable: {frontend_runtime_error}")
        else:
            if frontend_runtime.get("status") != "ok":
                status_value = "unknown"
                issues.append(f"/api/runtime/version status is {frontend_runtime.get('status')}")
            if frontend_runtime.get("git_sha") != release_git_sha:
                status_value = "drift_detected"
                issues.append(
                    f"/api/runtime/version git_sha mismatch ({frontend_runtime.get('git_sha')} != {release_git_sha})"
                )
            if frontend_runtime.get("release_id") != release_id:
                status_value = "drift_detected"
                issues.append(
                    f"/api/runtime/version release_id mismatch ({frontend_runtime.get('release_id')} != {release_id})"
                )
            if frontend_active_slot and frontend_runtime.get("frontend_slot") != frontend_active_slot:
                status_value = "drift_detected"
                issues.append(
                    f"/api/runtime/version frontend_slot mismatch ({frontend_runtime.get('frontend_slot')} != {frontend_active_slot})"
                )

        if n8n_compose_error:
            if status_value == "in_sync":
                status_value = "unknown"
            issues.append(n8n_compose_error)
        elif release_n8n_compose_sha256 and n8n_compose_sha256 != release_n8n_compose_sha256:
            status_value = "drift_detected"
            issues.append(f"n8n compose hash mismatch ({n8n_compose_sha256} != {release_n8n_compose_sha256})")

    return {
        "status": status_value,
        "origin_main": origin_main,
        "server_git_sha": current_meta.get("git_sha") if current_meta else None,
        "server_release_id": current_meta.get("release_id") if current_meta else None,
        "server_built_at": current_meta.get("built_at") if current_meta else None,
        "server_current_release_path": current_release_path,
        "backend_active_slot": backend_active_slot,
        "backend_active_slot_port": backend_active_slot_port,
        "backend_release_slot": current_meta.get("backend_slot") if current_meta else None,
        "backend_upstream_target": backend_upstream_target,
        "frontend_active_slot": frontend_active_slot,
        "frontend_active_slot_port": frontend_active_slot_port,
        "frontend_release_slot": current_meta.get("frontend_slot") if current_meta else None,
        "frontend_version_slot": frontend_runtime.get("frontend_slot") if frontend_runtime else None,
        "frontend_upstream_target": frontend_upstream_target,
        "n8n_compose_path": runtime_config["n8n_compose_path"],
        "n8n_compose_sha256": n8n_compose_sha256,
        "issues": issues,
    }


def _command_severity(status_value: str) -> str:
    if status_value == "drift_detected":
        return "warning"
    if status_value == "unknown":
        return "critical"
    return "info"


def _require_allowed_actor(actor: schemas.OpsCommandActor) -> None:
    allowed_chat_ids = settings.ops_command_allowed_chat_ids_list
    if actor.channel != "telegram":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported actor channel")
    if actor.role != "read_only":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported actor role")
    if not allowed_chat_ids or actor.id not in allowed_chat_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is not allowed")


def _help_response(request_id: str) -> schemas.OpsCommandResponse:
    command_rows = [
        "/ops help -> status.help",
        "/ops version -> status.version",
        "/ops drift -> status.drift",
        "/ops overview -> status.overview",
    ]
    return schemas.OpsCommandResponse(
        ok=True,
        command="status.help",
        summary="Supported /ops commands",
        details=command_rows,
        data={"commands": [{"command": key, "description": value} for key, value in SUPPORTED_COMMANDS.items()]},
        severity="info",
        request_id=request_id,
    )


def _version_response(request_id: str) -> schemas.OpsCommandResponse:
    payload = _build_version_payload()
    return schemas.OpsCommandResponse(
        ok=True,
        command="status.version",
        summary=f"Release {payload.get('release_id') or '-'} on backend={payload.get('backend_active_slot') or '-'} frontend={payload.get('frontend_active_slot') or '-'}",
        details=[
            f"git_sha={payload.get('git_sha') or '-'}",
            f"built_at={payload.get('built_at') or '-'}",
            f"backend_slot={payload.get('backend_slot') or '-'} active={payload.get('backend_active_slot') or '-'}",
            f"frontend_slot={payload.get('frontend_slot') or '-'} active={payload.get('frontend_active_slot') or '-'}",
        ],
        data=payload,
        severity="warning" if payload.get("status") != "ok" else "info",
        request_id=request_id,
    )


def _drift_response(request_id: str) -> schemas.OpsCommandResponse:
    payload = build_drift_report()
    detail_lines = payload["issues"][:8] if payload["issues"] else ["No drift detected."]
    return schemas.OpsCommandResponse(
        ok=True,
        command="status.drift",
        summary=f"Drift status: {payload['status']}",
        details=detail_lines,
        data=payload,
        severity=_command_severity(str(payload["status"])),
        request_id=request_id,
    )


def _overview_response(request_id: str) -> schemas.OpsCommandResponse:
    overview = get_ops_dashboard_overview()
    drift = build_drift_report()
    summary = (
        f"Overview {overview.overall_status}: "
        f"systemd={overview.summary.systemd_healthy}/{overview.summary.systemd_total}, "
        f"pm2_online={overview.summary.pm2_online}/{overview.summary.pm2_total}, "
        f"drift={drift['status']}"
    )
    details = [
        f"backend_active_slot={drift.get('backend_active_slot') or '-'}",
        f"frontend_active_slot={drift.get('frontend_active_slot') or '-'}",
    ]
    for warning in overview.warnings[:5]:
        details.append(warning)

    severity = "info"
    if overview.overall_status == "critical" or drift["status"] == "unknown":
        severity = "critical"
    elif overview.overall_status == "warning" or drift["status"] == "drift_detected":
        severity = "warning"

    return schemas.OpsCommandResponse(
        ok=True,
        command="status.overview",
        summary=summary,
        details=details,
        data={
            "overview": overview.model_dump(mode="json"),
            "drift": drift,
        },
        severity=severity,
        request_id=request_id,
    )


def execute_ops_command(request: schemas.OpsCommandRequest) -> schemas.OpsCommandResponse:
    _require_allowed_actor(request.actor)

    if request.command == "status.help":
        return _help_response(request.request_id)
    if request.command == "status.version":
        return _version_response(request.request_id)
    if request.command == "status.drift":
        return _drift_response(request.request_id)
    if request.command == "status.overview":
        return _overview_response(request.request_id)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported command: {request.command}. Use status.help.",
    )
