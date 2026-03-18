import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app import models
from backend.app.database import Base
from backend.app.seed import bootstrap_managed_apis


class SeedTests(unittest.TestCase):
    def test_bootstrap_managed_apis_inserts_defaults_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.db"
            engine = create_engine(f"sqlite:///{db_path}", future=True)
            Base.metadata.create_all(bind=engine)
            session_factory = sessionmaker(bind=engine, future=True)

            with patch("backend.app.seed.settings.managed_api_admin_base_url", "http://127.0.0.1:8000"), patch(
                "backend.app.seed.settings.managed_api_market_base_url",
                "http://127.0.0.1:8100",
            ):
                with session_factory() as db:
                    bootstrap_managed_apis(db)
                    first_pass = db.scalars(select(models.ManagedAPI).order_by(models.ManagedAPI.name)).all()

                    self.assertEqual(len(first_pass), 9)
                    self.assertEqual(first_pass[0].group_path, "platform/admin")

                    bootstrap_managed_apis(db)
                    second_pass = db.scalars(select(models.ManagedAPI).order_by(models.ManagedAPI.name)).all()

                    self.assertEqual(len(second_pass), 9)


if __name__ == "__main__":
    unittest.main()
