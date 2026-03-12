import unittest
from unittest.mock import patch

from backend.app import schemas
from backend.app.services import ops_dashboard_service


def make_process(
    name: str,
    *,
    status: str = "online",
    restart_count: int = 0,
) -> schemas.OpsProcessStatusResponse:
    return schemas.OpsProcessStatusResponse(
        name=name,
        status=status,
        is_healthy=status == "online",
        attention_level=ops_dashboard_service._attention_level_for_pm2_process(status, restart_count),
        group_key="other",
        group_label="Other",
        pid=None,
        restart_count=restart_count,
        cpu_percent=0,
        memory_bytes=0,
        uptime_seconds=None,
        cwd=None,
    )


class OpsDashboardServiceTests(unittest.TestCase):
    def test_sanitize_log_lines_filters_pm2_banners_and_keeps_recent_lines(self) -> None:
        lines = ops_dashboard_service._sanitize_log_lines(
            "\n".join(
                [
                    "[TAILING] Tailing last 30 lines",
                    "[PM2] Some banner",
                    "2026-03-12T00:00:01 line-1",
                    "2026-03-12T00:00:02 line-2",
                ]
            ),
            limit=1,
        )

        self.assertEqual(lines, ["2026-03-12T00:00:02 line-2"])

    def test_host_metric_status_uses_thresholds(self) -> None:
        self.assertEqual(ops_dashboard_service._host_metric_status_for_percent(None), "unavailable")
        self.assertEqual(ops_dashboard_service._host_metric_status_for_percent(42.0), "healthy")
        self.assertEqual(ops_dashboard_service._host_metric_status_for_percent(75.0), "warning")
        self.assertEqual(ops_dashboard_service._host_metric_status_for_percent(90.0), "critical")

    def test_calculate_cpu_usage_percent_uses_snapshot_delta(self) -> None:
        usage_percent = ops_dashboard_service._calculate_cpu_usage_percent((100, 1000), (160, 1200))
        self.assertEqual(usage_percent, 70.0)

    def test_parse_meminfo_uses_memavailable(self) -> None:
        total_bytes, available_bytes = ops_dashboard_service._parse_meminfo(
            "MemTotal:       1024000 kB\nMemAvailable:    256000 kB\n"
        )

        self.assertEqual(total_bytes, 1024000 * 1024)
        self.assertEqual(available_bytes, 256000 * 1024)

    @patch("backend.app.services.ops_dashboard_service.time.sleep", return_value=None)
    @patch(
        "backend.app.services.ops_dashboard_service._read_cpu_snapshot",
        side_effect=[(100, 1000), (160, 1200)],
    )
    def test_collect_host_cpu_metrics_returns_usage(self, _read_cpu_snapshot: object, _sleep: object) -> None:
        metrics, warnings = ops_dashboard_service._collect_host_cpu_metrics()

        self.assertEqual(metrics.usage_percent, 70.0)
        self.assertEqual(metrics.status, "healthy")
        self.assertEqual(warnings, [])

    @patch("backend.app.services.ops_dashboard_service._run_command")
    @patch("backend.app.services.ops_dashboard_service._find_command", return_value="/usr/bin/journalctl")
    @patch.object(ops_dashboard_service.settings, "ops_systemd_units", "svc-a,svc-b")
    def test_collect_systemd_runtime_logs_builds_sources(
        self,
        _find_command: object,
        run_command: object,
    ) -> None:
        run_command.side_effect = [
            ops_dashboard_service.CommandResult(stdout="2026-03-12 svc-a line", stderr="", returncode=0),
            ops_dashboard_service.CommandResult(stdout="2026-03-12 svc-b line", stderr="", returncode=0),
        ]

        sources, warnings = ops_dashboard_service._collect_systemd_runtime_logs(line_count=30)

        self.assertEqual([item.source_name for item in sources], ["svc-a", "svc-b"])
        self.assertTrue(all(item.status == "available" for item in sources))
        self.assertEqual(sources[0].lines, ["2026-03-12 svc-a line"])
        self.assertEqual(warnings, [])

    @patch("backend.app.services.ops_dashboard_service._run_command")
    @patch("backend.app.services.ops_dashboard_service._find_command", return_value="/usr/bin/pm2")
    @patch("backend.app.services.ops_dashboard_service._collect_pm2_processes")
    def test_collect_pm2_runtime_logs_marks_unavailable_source_on_failure(
        self,
        collect_pm2_processes: object,
        _find_command: object,
        run_command: object,
    ) -> None:
        collect_pm2_processes.return_value = (
            [
                make_process("bot-a"),
            ],
            [],
        )
        run_command.return_value = ops_dashboard_service.CommandResult(stdout="", stderr="boom", returncode=1)

        sources, warnings = ops_dashboard_service._collect_pm2_runtime_logs(line_count=30)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_name, "bot-a")
        self.assertEqual(sources[0].status, "unavailable")
        self.assertIn("pm2 log tail failed: bot-a", warnings)

    @patch("backend.app.services.ops_dashboard_service._collect_pm2_runtime_logs")
    @patch("backend.app.services.ops_dashboard_service._collect_systemd_runtime_logs")
    def test_get_runtime_logs_combines_sources_and_warnings(
        self,
        collect_systemd_runtime_logs: object,
        collect_pm2_runtime_logs: object,
    ) -> None:
        collect_systemd_runtime_logs.return_value = (
            [
                schemas.RuntimeLogSourceResponse(
                    source_name="svc-a",
                    source_type="systemd",
                    status="available",
                    lines=["a"],
                )
            ],
            ["systemd warning"],
        )
        collect_pm2_runtime_logs.return_value = (
            [
                schemas.RuntimeLogSourceResponse(
                    source_name="bot-a",
                    source_type="pm2",
                    status="available",
                    lines=["b"],
                )
            ],
            ["pm2 warning"],
        )

        response = ops_dashboard_service.get_runtime_logs()

        self.assertEqual(response.systemd_logs[0].source_name, "svc-a")
        self.assertEqual(response.pm2_logs[0].source_name, "bot-a")
        self.assertEqual(response.warnings, ["systemd warning", "pm2 warning"])

    @patch("backend.app.services.ops_dashboard_service._collect_host_disk_metrics")
    @patch("backend.app.services.ops_dashboard_service._collect_host_memory_metrics")
    @patch("backend.app.services.ops_dashboard_service._collect_host_cpu_metrics")
    @patch("backend.app.services.ops_dashboard_service._collect_pm2_processes")
    @patch("backend.app.services.ops_dashboard_service._collect_systemd_services")
    def test_overview_includes_host_metric_warnings_without_failing(
        self,
        systemd_mock: object,
        pm2_mock: object,
        cpu_mock: object,
        memory_mock: object,
        disk_mock: object,
    ) -> None:
        systemd_mock.return_value = ([], [])
        pm2_mock.return_value = ([], [])
        cpu_mock.return_value = (
            schemas.HostCpuMetricsResponse(usage_percent=None, status="unavailable"),
            ["host cpu metrics unavailable: test"],
        )
        memory_mock.return_value = (
            schemas.HostMemoryMetricsResponse(
                total_bytes=100,
                used_bytes=40,
                available_bytes=60,
                usage_percent=40.0,
                status="healthy",
            ),
            [],
        )
        disk_mock.return_value = (
            schemas.HostDiskMetricsResponse(
                mount_path="/",
                total_bytes=100,
                used_bytes=10,
                free_bytes=90,
                usage_percent=10.0,
                status="healthy",
            ),
            [],
        )

        overview = ops_dashboard_service.get_ops_dashboard_overview()

        self.assertEqual(overview.host_metrics.cpu.status, "unavailable")
        self.assertIn("host cpu metrics unavailable: test", overview.warnings)

    def test_common_prefix_groups_processes_by_first_remaining_token(self) -> None:
        processes = [
            make_process("btcore-monitor"),
            make_process("btcore-monitor-tp1"),
            make_process("btcore-signal-ingest"),
            make_process("btcore-incident-drafts"),
        ]

        decorated = ops_dashboard_service._decorate_pm2_processes(processes)

        grouped = {item.name: (item.group_key, item.group_label) for item in decorated}
        self.assertEqual(grouped["btcore-monitor"], ("monitor", "Monitor"))
        self.assertEqual(grouped["btcore-monitor-tp1"], ("monitor", "Monitor"))
        self.assertEqual(grouped["btcore-signal-ingest"], ("signal", "Signal"))
        self.assertEqual(grouped["btcore-incident-drafts"], ("incident", "Incident"))

    def test_missing_common_prefix_falls_back_to_other_group(self) -> None:
        processes = [
            make_process("monitor"),
            make_process("incident-drafts"),
        ]

        decorated = ops_dashboard_service._decorate_pm2_processes(processes)

        self.assertTrue(all(item.group_key == "other" for item in decorated))
        self.assertTrue(all(item.group_label == "Other" for item in decorated))

    def test_shared_platform_prefix_does_not_consume_group_name(self) -> None:
        processes = [
            make_process("btcore-worker-a"),
            make_process("btcore-worker-b"),
        ]

        decorated = ops_dashboard_service._decorate_pm2_processes(processes)

        self.assertEqual([item.group_key for item in decorated], ["worker", "worker"])

    def test_attention_levels_follow_status_then_restart_count(self) -> None:
        self.assertEqual(ops_dashboard_service._attention_level_for_pm2_process("offline", 0), "critical")
        self.assertEqual(ops_dashboard_service._attention_level_for_pm2_process("online", 2), "warning")
        self.assertEqual(ops_dashboard_service._attention_level_for_pm2_process("online", 0), "healthy")

    def test_sorting_prioritizes_critical_then_warning_then_healthy(self) -> None:
        processes = [
            make_process("btcore-worker-b", status="online", restart_count=0),
            make_process("btcore-worker-a", status="online", restart_count=3),
            make_process("btcore-worker-c", status="errored", restart_count=0),
            make_process("btcore-worker-d", status="online", restart_count=1),
        ]

        decorated = ops_dashboard_service._decorate_pm2_processes(processes)

        self.assertEqual(
            [item.name for item in decorated],
            [
                "btcore-worker-c",
                "btcore-worker-a",
                "btcore-worker-d",
                "btcore-worker-b",
            ],
        )


if __name__ == "__main__":
    unittest.main()
