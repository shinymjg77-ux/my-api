import unittest

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
