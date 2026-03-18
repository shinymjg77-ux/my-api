import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import schemas
from backend.app.config import settings
from backend.app.database import Base, get_db
from backend.app.main import app


class JobsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "app.db"
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, future=True)

        def override_get_db():
            with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_ops_check_requires_job_secret(self) -> None:
        response = self.client.get("/api/v1/jobs/ops-check")
        self.assertEqual(response.status_code, 401)

    def test_ops_check_returns_response_with_valid_secret(self) -> None:
        payload = schemas.OpsCheckResponse(
            generated_at="2026-03-18T00:00:00Z",
            overall_status="healthy",
            previous_overall_status=None,
            changed=False,
            summary="All tracked services and host metrics are healthy.",
            issues=[],
        )

        with patch("backend.app.routers.jobs.run_ops_check", return_value=payload):
            response = self.client.get(
                "/api/v1/jobs/ops-check",
                headers={"X-Job-Secret": settings.job_shared_secret},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["overall_status"], "healthy")


if __name__ == "__main__":
    unittest.main()
