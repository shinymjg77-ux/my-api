import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .. import schemas


SYSTEMCTL_PROPERTIES = ("Id", "Description", "ActiveState", "SubState")


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


def _parse_pm2_process(item: dict) -> schemas.OpsProcessStatusResponse:
    pm2_env = item.get("pm2_env") or {}
    monit = item.get("monit") or {}
    uptime_ms = pm2_env.get("pm_uptime")

    uptime_seconds: int | None = None
    if isinstance(uptime_ms, (int, float)):
        uptime_seconds = max(0, int((datetime.now(timezone.utc).timestamp() * 1000 - uptime_ms) / 1000))

    status = str(pm2_env.get("status") or "unknown")
    pid = item.get("pid")

    return schemas.OpsProcessStatusResponse(
        name=str(item.get("name") or "unknown"),
        status=status,
        is_healthy=status == "online",
        pid=pid if isinstance(pid, int) and pid > 0 else None,
        restart_count=int(pm2_env.get("restart_time") or 0),
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

    return [_parse_pm2_process(item) for item in payload if isinstance(item, dict)], warnings


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
