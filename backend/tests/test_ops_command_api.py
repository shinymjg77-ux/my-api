import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app


class OpsCommandApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.original_secret = settings.ops_command_shared_secret
        self.original_chat_ids = settings.ops_command_allowed_chat_ids
        settings.ops_command_shared_secret = "ops-command-secret-for-tests"
        settings.ops_command_allowed_chat_ids = "8349784231"

    def tearDown(self) -> None:
        settings.ops_command_shared_secret = self.original_secret
        settings.ops_command_allowed_chat_ids = self.original_chat_ids

    def _payload(self, *, command: str = "status.help", actor_id: str = "8349784231") -> dict:
        return {
            "command": command,
            "arguments": {},
            "request_id": "req-123",
            "source": "n8n",
            "actor": {
                "id": actor_id,
                "name": "junlab",
                "channel": "telegram",
                "role": "read_only",
            },
        }

    def test_ops_command_requires_secret(self) -> None:
        response = self.client.post("/api/v1/ops/command", json=self._payload())
        self.assertEqual(response.status_code, 401)

    def test_ops_command_rejects_disallowed_chat_id(self) -> None:
        response = self.client.post(
            "/api/v1/ops/command",
            json=self._payload(actor_id="999999"),
            headers={"X-Ops-Command-Secret": settings.ops_command_shared_secret},
        )

        self.assertEqual(response.status_code, 403)

    def test_ops_command_returns_help_payload(self) -> None:
        response = self.client.post(
            "/api/v1/ops/command",
            json=self._payload(),
            headers={"X-Ops-Command-Secret": settings.ops_command_shared_secret},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["command"], "status.help")
        self.assertEqual(response.json()["severity"], "info")
        self.assertIn("/ops version -> status.version", response.json()["details"])

    def test_ops_command_returns_version_payload(self) -> None:
        version_payload = {
            "status": "ok",
            "git_sha": "abc123",
            "release_id": "20260319T123456Z",
            "built_at": "2026-03-19T12:34:56Z",
            "backend_slot": "green",
            "frontend_slot": "blue",
            "backend_active_slot": "green",
            "frontend_active_slot": "blue",
            "frontend_runtime_status": "ok",
            "frontend_runtime_error": None,
            "missing_release_meta": False,
            "release_meta_error": None,
        }

        with patch("backend.app.services.ops_command_service._build_version_payload", return_value=version_payload):
            response = self.client.post(
                "/api/v1/ops/command",
                json=self._payload(command="status.version"),
                headers={"X-Ops-Command-Secret": settings.ops_command_shared_secret},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["command"], "status.version")
        self.assertEqual(response.json()["data"]["release_id"], "20260319T123456Z")
        self.assertEqual(response.json()["data"]["frontend_slot"], "blue")

    def test_ops_command_rejects_unknown_command(self) -> None:
        response = self.client.post(
            "/api/v1/ops/command",
            json=self._payload(command="status.unknown"),
            headers={"X-Ops-Command-Secret": settings.ops_command_shared_secret},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported command", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
