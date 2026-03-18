import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import schemas
from backend.app.database import Base
from backend.app.services.ops_check_service import run_ops_check


def make_overview(
    *,
    overall_status: str = "healthy",
    systemd_services: list[schemas.OpsServiceStatusResponse] | None = None,
    pm2_processes: list[schemas.OpsProcessStatusResponse] | None = None,
    cpu_status: str = "healthy",
    cpu_usage: float | None = 20.0,
    memory_status: str = "healthy",
    memory_usage: float | None = 30.0,
    disk_status: str = "healthy",
    disk_usage: float | None = 40.0,
    warnings: list[str] | None = None,
) -> schemas.OpsDashboardResponse:
    return schemas.OpsDashboardResponse(
        generated_at="2026-03-18T00:00:00Z",
        overall_status=overall_status,
        systemd_services=systemd_services or [],
        pm2_processes=pm2_processes or [],
        host_metrics=schemas.HostMetricsResponse(
            cpu=schemas.HostCpuMetricsResponse(
                usage_percent=cpu_usage,
                status=cpu_status,
            ),
            memory=schemas.HostMemoryMetricsResponse(
                total_bytes=100,
                used_bytes=30,
                available_bytes=70,
                usage_percent=memory_usage,
                status=memory_status,
            ),
            disk=schemas.HostDiskMetricsResponse(
                mount_path="/",
                total_bytes=100,
                used_bytes=40,
                free_bytes=60,
                usage_percent=disk_usage,
                status=disk_status,
            ),
        ),
        summary=schemas.OpsDashboardSummaryResponse(
            systemd_total=len(systemd_services or []),
            systemd_healthy=sum(1 for item in (systemd_services or []) if item.is_healthy),
            pm2_total=len(pm2_processes or []),
            pm2_online=sum(1 for item in (pm2_processes or []) if item.status == "online"),
            pm2_unhealthy=sum(1 for item in (pm2_processes or []) if item.attention_level != "healthy"),
        ),
        warnings=warnings or [],
    )


class OpsCheckServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "app.db"
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, future=True)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_first_run_records_state_without_marking_changed(self) -> None:
        overview = make_overview(
            overall_status="critical",
            systemd_services=[
                schemas.OpsServiceStatusResponse(
                    name="personal-market-api.service",
                    description="Market API",
                    active_state="failed",
                    sub_state="failed",
                    is_healthy=False,
                )
            ],
        )

        with self.session_factory() as db:
            with patch("backend.app.services.ops_check_service.get_ops_dashboard_overview", return_value=overview):
                response = run_ops_check(db)

                self.assertEqual(response.overall_status, "critical")
                self.assertIsNone(response.previous_overall_status)
                self.assertFalse(response.changed)
                self.assertEqual(len(response.issues), 1)
                self.assertEqual(response.issues[0].source_type, "systemd")

    def test_second_identical_run_stays_unchanged(self) -> None:
        overview = make_overview(
            overall_status="warning",
            pm2_processes=[
                schemas.OpsProcessStatusResponse(
                    name="btcore-worker",
                    status="online",
                    is_healthy=True,
                    attention_level="warning",
                    group_key="worker",
                    group_label="Worker",
                    pid=123,
                    restart_count=3,
                    cpu_percent=10.0,
                    memory_bytes=100,
                    uptime_seconds=30,
                    cwd="/srv/app",
                )
            ],
        )

        with self.session_factory() as db:
            with patch("backend.app.services.ops_check_service.get_ops_dashboard_overview", return_value=overview):
                first = run_ops_check(db)
                second = run_ops_check(db)

                self.assertFalse(first.changed)
                self.assertEqual(second.previous_overall_status, "warning")
                self.assertFalse(second.changed)

    def test_issue_change_marks_response_changed(self) -> None:
        healthy = make_overview(overall_status="healthy")
        warning = make_overview(
            overall_status="warning",
            disk_status="warning",
            disk_usage=80.0,
        )

        with self.session_factory() as db:
            with patch("backend.app.services.ops_check_service.get_ops_dashboard_overview", return_value=healthy):
                run_ops_check(db)

            with patch("backend.app.services.ops_check_service.get_ops_dashboard_overview", return_value=warning):
                response = run_ops_check(db)

                self.assertEqual(response.previous_overall_status, "healthy")
                self.assertTrue(response.changed)
                self.assertEqual(response.issues[0].source_type, "host")
                self.assertEqual(response.issues[0].source_name, "disk")

    def test_same_warning_bucket_with_different_metric_value_stays_unchanged(self) -> None:
        first_overview = make_overview(
            overall_status="healthy",
            disk_status="warning",
            disk_usage=80.0,
        )
        second_overview = make_overview(
            overall_status="healthy",
            disk_status="warning",
            disk_usage=81.2,
        )

        with self.session_factory() as db:
            with patch("backend.app.services.ops_check_service.get_ops_dashboard_overview", return_value=first_overview):
                run_ops_check(db)

            with patch("backend.app.services.ops_check_service.get_ops_dashboard_overview", return_value=second_overview):
                response = run_ops_check(db)

                self.assertEqual(response.overall_status, "warning")
                self.assertFalse(response.changed)

    def test_collector_warnings_are_exposed_as_warning_issues(self) -> None:
        overview = make_overview(
            overall_status="healthy",
            warnings=["pm2 unavailable"],
        )

        with self.session_factory() as db:
            with patch("backend.app.services.ops_check_service.get_ops_dashboard_overview", return_value=overview):
                response = run_ops_check(db)

                self.assertEqual(response.overall_status, "warning")
                self.assertEqual(len(response.issues), 1)
                self.assertEqual(response.issues[0].source_type, "collector")
                self.assertEqual(response.issues[0].severity, "warning")


if __name__ == "__main__":
    unittest.main()
