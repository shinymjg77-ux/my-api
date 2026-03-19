import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.release_meta import load_release_meta


class ReleaseMetaTests(unittest.TestCase):
    def test_load_release_meta_returns_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            meta_path = Path(temp_dir) / ".release-meta.json"
            meta_path.write_text(
                json.dumps(
                    {
                        "git_sha": "abc123",
                        "release_id": "20260319T010203Z",
                        "built_at": "2026-03-19T01:02:03Z",
                        "backend_slot": "green",
                    }
                ),
                encoding="utf-8",
            )

            meta, error = load_release_meta(meta_path)

        self.assertEqual(error, None)
        self.assertEqual(
            meta,
            {
                "git_sha": "abc123",
                "release_id": "20260319T010203Z",
                "built_at": "2026-03-19T01:02:03Z",
                "backend_slot": "green",
            },
        )

    def test_load_release_meta_reports_invalid_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            meta_path = Path(temp_dir) / ".release-meta.json"
            meta_path.write_text(json.dumps({"git_sha": "abc123"}), encoding="utf-8")

            meta, error = load_release_meta(meta_path)

        self.assertEqual(meta, None)
        self.assertEqual(error, "invalid_shape")

    def test_version_endpoint_returns_release_metadata(self) -> None:
        client = TestClient(app)

        with patch(
            "backend.app.main.load_release_meta",
            return_value=(
                {
                    "git_sha": "abc123",
                    "release_id": "20260319T010203Z",
                    "built_at": "2026-03-19T01:02:03Z",
                    "backend_slot": "green",
                },
                None,
            ),
        ):
            response = client.get("/version")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["git_sha"], "abc123")
        self.assertEqual(response.json()["backend_slot"], "green")
        self.assertFalse(response.json()["missing_release_meta"])

    def test_version_endpoint_returns_degraded_payload_when_metadata_is_missing(self) -> None:
        client = TestClient(app)

        with patch("backend.app.main.load_release_meta", return_value=(None, "missing")):
            response = client.get("/version")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "degraded")
        self.assertEqual(response.json()["release_meta_error"], "missing")
        self.assertTrue(response.json()["missing_release_meta"])
        self.assertEqual(response.json()["git_sha"], None)


if __name__ == "__main__":
    unittest.main()
