import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import crud, schemas
from .ops_dashboard_service import get_ops_dashboard_overview


OPS_CHECK_NAME = "default"


def _overall_status_for_issues(
    issues: list[schemas.OpsCheckIssueResponse],
) -> str:
    if any(item.severity == "critical" for item in issues):
        return "critical"
    if any(item.severity == "warning" for item in issues):
        return "warning"
    return "healthy"


def _build_summary(issues: list[schemas.OpsCheckIssueResponse]) -> str:
    if not issues:
        return "All tracked services and host metrics are healthy."

    critical_count = sum(1 for item in issues if item.severity == "critical")
    warning_count = sum(1 for item in issues if item.severity == "warning")
    parts: list[str] = []
    if critical_count:
        parts.append(f"{critical_count} critical")
    if warning_count:
        parts.append(f"{warning_count} warning")
    return f"{', '.join(parts)} issue(s) detected."


def _fingerprint_for_issues(
    overall_status: str,
    issues: list[schemas.OpsCheckIssueResponse],
) -> str:
    def fingerprint_key(item: schemas.OpsCheckIssueResponse) -> str:
        base = [item.severity, item.source_type, item.source_name]
        if item.source_type in {"systemd", "collector"}:
            base.append(item.message)
        return "|".join(base)

    payload = [
        overall_status,
        *sorted(fingerprint_key(item) for item in issues),
    ]
    return hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest()


def _build_ops_issues(overview: schemas.OpsDashboardResponse) -> list[schemas.OpsCheckIssueResponse]:
    issues: list[schemas.OpsCheckIssueResponse] = []

    for service in overview.systemd_services:
        if service.is_healthy:
            continue
        issues.append(
            schemas.OpsCheckIssueResponse(
                source_type="systemd",
                source_name=service.name,
                severity="critical",
                message=f"{service.description or service.name} is {service.active_state}/{service.sub_state}",
            )
        )

    for process in overview.pm2_processes:
        if process.attention_level == "healthy":
            continue
        issues.append(
            schemas.OpsCheckIssueResponse(
                source_type="pm2",
                source_name=process.name,
                severity="critical" if process.attention_level == "critical" else "warning",
                message=(
                    f"status={process.status}, restart_count={process.restart_count}, "
                    f"cpu={process.cpu_percent:.1f}%"
                ),
            )
        )

    host_metrics = {
        "cpu": overview.host_metrics.cpu,
        "memory": overview.host_metrics.memory,
        "disk": overview.host_metrics.disk,
    }
    for name, metric in host_metrics.items():
        status = metric.status
        if status not in {"warning", "critical"}:
            continue

        usage_percent = getattr(metric, "usage_percent", None)
        usage_text = "unknown" if usage_percent is None else f"{usage_percent:.1f}%"
        issues.append(
            schemas.OpsCheckIssueResponse(
                source_type="host",
                source_name=name,
                severity=status,
                message=f"{name} usage is {usage_text}",
            )
        )

    for warning in overview.warnings:
        issues.append(
            schemas.OpsCheckIssueResponse(
                source_type="collector",
                source_name="ops-dashboard",
                severity="warning",
                message=warning,
            )
        )

    severity_order = {"critical": 0, "warning": 1}
    return sorted(
        issues,
        key=lambda item: (
            severity_order[item.severity],
            item.source_type,
            item.source_name.lower(),
            item.message.lower(),
        ),
    )


def run_ops_check(db: Session) -> schemas.OpsCheckResponse:
    generated_at = datetime.now(timezone.utc)
    overview = get_ops_dashboard_overview()
    issues = _build_ops_issues(overview)
    overall_status = _overall_status_for_issues(issues)
    summary = _build_summary(issues)
    fingerprint = _fingerprint_for_issues(overall_status, issues)

    previous = crud.get_ops_check_state(db, OPS_CHECK_NAME)
    previous_status = previous.overall_status if previous else None

    if previous is None:
        changed = False
    else:
        changed = (
            previous.overall_status != overall_status
            or previous.fingerprint != fingerprint
        )

    crud.upsert_ops_check_state(
        db,
        check_name=OPS_CHECK_NAME,
        overall_status=overall_status,
        fingerprint=fingerprint,
        checked_at=generated_at,
    )

    return schemas.OpsCheckResponse(
        generated_at=generated_at,
        overall_status=overall_status,
        previous_overall_status=previous_status,
        changed=changed,
        summary=summary,
        issues=issues,
    )
