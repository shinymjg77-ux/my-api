import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ..config import settings
from .. import schemas


SYSTEMCTL_PROPERTIES = ("Id", "Description", "ActiveState", "SubState")
PM2_ATTENTION_ORDER = {
    "critical": 0,
    "warning": 1,
    "healthy": 2,
}


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


def _find_command(name: str, fallbacks: tuple[str, ...]) -> str | None:
    found = shutil.which(name)
    if found:
        return found

    for candidate in fallbacks:
        if Path(candidate).exists():
            return candidate

    return None


def _run_command(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 10) -> CommandResult:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
        returncode=completed.returncode,
    )


def _collect_systemd_services() -> tuple[list[schemas.OpsServiceStatusResponse], list[str]]:
    warnings: list[str] = []
    systemctl_bin = _find_command("systemctl", ("/usr/bin/systemctl",))
    if not systemctl_bin:
        return [], ["systemctl unavailable"]

    services: list[schemas.OpsServiceStatusResponse] = []
    for unit in settings.ops_systemd_units_list:
        result = _run_command(
            [
                systemctl_bin,
                "show",
                unit,
                "--property",
                ",".join(SYSTEMCTL_PROPERTIES),
                "--value",
            ]
        )
        if result.returncode != 0:
            warnings.append(f"systemd lookup failed: {unit}")
            services.append(
                schemas.OpsServiceStatusResponse(
                    name=unit,
                    description="Lookup failed",
                    active_state="unknown",
                    sub_state="unknown",
                    is_healthy=False,
                )
            )
            continue

        values = result.stdout.splitlines()
        parsed = dict(zip(SYSTEMCTL_PROPERTIES, values, strict=False))
        active_state = parsed.get("ActiveState", "unknown")
        sub_state = parsed.get("SubState", "unknown")
        services.append(
            schemas.OpsServiceStatusResponse(
                name=parsed.get("Id", unit) or unit,
                description=parsed.get("Description", "") or "",
                active_state=active_state,
                sub_state=sub_state,
                is_healthy=active_state == "active",
            )
        )

    return services, warnings


def _attention_level_for_pm2_process(status: str, restart_count: int) -> Literal["healthy", "warning", "critical"]:
    normalized_status = status.lower()
    if normalized_status != "online":
        return "critical"
    if restart_count >= 1:
        return "warning"
    return "healthy"


def _common_pm2_name_prefix(names: list[str]) -> str | None:
    tokenized_names = [[part for part in name.split("-") if part] for name in names if name]
    if len(tokenized_names) < 2:
        return None

    first_token = tokenized_names[0][0] if tokenized_names[0] else ""
    if not first_token:
        return None
    if not all(parts and parts[0] == first_token for parts in tokenized_names[1:]):
        return None
    return first_token


def _pm2_group_key_for_name(name: str, common_prefix: str | None) -> str:
    if not common_prefix:
        return "other"

    prefix_with_dash = f"{common_prefix}-"
    if name.startswith(prefix_with_dash):
        remainder = name[len(prefix_with_dash):]
    elif name == common_prefix:
        remainder = ""
    else:
        return "other"

    token = next((part.strip().lower() for part in remainder.split("-") if part.strip()), "")
    return token or "other"


def _pm2_group_label(group_key: str) -> str:
    if group_key == "other":
        return "Other"
    return " ".join(part.capitalize() for part in group_key.replace("_", "-").split("-") if part)


def _decorate_pm2_processes(
    processes: list[schemas.OpsProcessStatusResponse],
) -> list[schemas.OpsProcessStatusResponse]:
    common_prefix = _common_pm2_name_prefix([process.name for process in processes])
    decorated: list[schemas.OpsProcessStatusResponse] = []
    for process in processes:
        group_key = _pm2_group_key_for_name(process.name, common_prefix)
        decorated.append(
            process.model_copy(
                update={
                    "attention_level": _attention_level_for_pm2_process(process.status, process.restart_count),
                    "group_key": group_key,
                    "group_label": _pm2_group_label(group_key),
                }
            )
        )
    return sorted(
        decorated,
        key=lambda item: (
            PM2_ATTENTION_ORDER[item.attention_level],
            -item.restart_count,
            item.name.lower(),
        ),
    )


def _parse_pm2_process(item: dict) -> schemas.OpsProcessStatusResponse:
    pm2_env = item.get("pm2_env") or {}
    monit = item.get("monit") or {}
    uptime_ms = pm2_env.get("pm_uptime")

    uptime_seconds: int | None = None
    if isinstance(uptime_ms, (int, float)):
        uptime_seconds = max(0, int((datetime.now(timezone.utc).timestamp() * 1000 - uptime_ms) / 1000))

    status = str(pm2_env.get("status") or "unknown").lower()
    pid = item.get("pid")
    restart_count = int(pm2_env.get("restart_time") or 0)

    return schemas.OpsProcessStatusResponse(
        name=str(item.get("name") or "unknown"),
        status=status,
        is_healthy=status == "online",
        attention_level=_attention_level_for_pm2_process(status, restart_count),
        group_key="other",
        group_label="Other",
        pid=pid if isinstance(pid, int) and pid > 0 else None,
        restart_count=restart_count,
        cpu_percent=float(monit.get("cpu") or 0),
        memory_bytes=int(monit.get("memory") or 0),
        uptime_seconds=uptime_seconds,
        cwd=pm2_env.get("pm_cwd") or pm2_env.get("cwd"),
    )


def _collect_pm2_processes() -> tuple[list[schemas.OpsProcessStatusResponse], list[str]]:
    warnings: list[str] = []
    pm2_bin = _find_command("pm2", ("/usr/local/bin/pm2", "/usr/bin/pm2"))
    if not pm2_bin:
        return [], ["pm2 unavailable"]

    env = os.environ.copy()
    env.setdefault("PM2_HOME", str(Path.home() / ".pm2"))

    result = _run_command([pm2_bin, "jlist"], env=env, timeout=15)
    if result.returncode != 0:
        return [], [f"pm2 lookup failed: {result.stderr or 'unknown error'}"]

    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return [], ["pm2 returned invalid JSON"]

    if not isinstance(payload, list):
        return [], ["pm2 returned unexpected payload"]

    parsed_processes = [_parse_pm2_process(item) for item in payload if isinstance(item, dict)]
    return _decorate_pm2_processes(parsed_processes), warnings


def get_ops_dashboard_overview() -> schemas.OpsDashboardResponse:
    generated_at = datetime.now(timezone.utc)
    systemd_services, systemd_warnings = _collect_systemd_services()
    pm2_processes, pm2_warnings = _collect_pm2_processes()
    warnings = [*systemd_warnings, *pm2_warnings]

    systemd_healthy = sum(1 for item in systemd_services if item.is_healthy)
    pm2_online = sum(1 for item in pm2_processes if item.is_healthy)
    pm2_unhealthy = len(pm2_processes) - pm2_online

    if any(not item.is_healthy for item in systemd_services):
        overall_status = "critical"
    elif pm2_unhealthy > 0 or warnings:
        overall_status = "warning"
    else:
        overall_status = "healthy"

    return schemas.OpsDashboardResponse(
        generated_at=generated_at,
        overall_status=overall_status,
        systemd_services=systemd_services,
        pm2_processes=pm2_processes,
        summary=schemas.OpsDashboardSummaryResponse(
            systemd_total=len(systemd_services),
            systemd_healthy=systemd_healthy,
            pm2_total=len(pm2_processes),
            pm2_online=pm2_online,
            pm2_unhealthy=pm2_unhealthy,
        ),
        warnings=warnings,
    )
