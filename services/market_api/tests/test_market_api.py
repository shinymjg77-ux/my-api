import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.market_api.app import crud, deps, schemas
from services.market_api.app.database import Base
from services.market_api.app.routers import market


class MarketApiTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        self.engine = create_engine(f"sqlite:///{handle.name}", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_job_secret_is_required(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            deps.require_job_secret(None)
        self.assertEqual(exc.exception.status_code, 401)

    @patch.object(deps.settings, "job_shared_secret", "test-job-secret")
    @patch(
        "services.market_api.app.routers.market.market_service.run_rsi_check",
        return_value=schemas.RSICheckResponse(
            symbol="QLD",
            target_session_date=date(2026, 3, 17),
            should_send=True,
            skip_reason=None,
            close=104.25,
            change=-1.5,
            change_pct=-1.42,
            rsi=28.4,
            previous_rsi=31.15,
            rsi_change=-2.75,
            threshold=30.0,
            state="UNDER_30",
            previous_state="ABOVE_30",
            changed=True,
            event="ENTER_UNDER_30",
            market_date=date(2026, 3, 17),
            checked_at=datetime(2026, 3, 18, 0, 0, tzinfo=timezone.utc),
        ),
    )
    def test_rsi_check_returns_structured_payload(self, _run_rsi_check: object) -> None:
        with self.SessionLocal() as db:
            response = market.run_rsi_check("test-job-secret", db)

        self.assertEqual(response.symbol, "QLD")
        self.assertEqual(response.close, 104.25)
        self.assertEqual(response.change, -1.5)
        self.assertEqual(response.change_pct, -1.42)
        self.assertEqual(response.previous_rsi, 31.15)
        self.assertEqual(response.rsi_change, -2.75)
        self.assertEqual(response.event, "ENTER_UNDER_30")
        self.assertTrue(response.changed)

    @patch.object(deps.settings, "job_shared_secret", "test-job-secret")
    @patch(
        "services.market_api.app.routers.market.market_service.run_distribution_deadline_check",
        return_value=schemas.DistributionDeadlineCheckResponse(
            generated_at=datetime(2026, 4, 7, 20, 30, tzinfo=timezone.utc),
            funds=[
                schemas.DistributionDeadlineFundResponse(
                    symbol="XQQI",
                    source_url="https://neosfunds.com/xqqi/",
                    declaration_date=date(2026, 4, 7),
                    ex_dividend_date=date(2026, 4, 8),
                    record_date=date(2026, 4, 8),
                    payable_date=date(2026, 4, 10),
                    distribution_amount=None,
                    eligible_session_start_et=datetime(2026, 4, 7, 9, 30, tzinfo=timezone.utc),
                    eligible_session_end_et=datetime(2026, 4, 7, 16, 0, tzinfo=timezone.utc),
                    eligible_session_start_kst=datetime(2026, 4, 7, 22, 30, tzinfo=timezone.utc),
                    eligible_session_end_kst=datetime(2026, 4, 8, 5, 0, tzinfo=timezone.utc),
                    alert_kst_date=date(2026, 4, 7),
                    is_alert_day_kst=True,
                    deadline_kst_date=date(2026, 4, 8),
                    is_deadline_day_kst=False,
                    alert_due=True,
                )
            ],
        ),
    )
    def test_distribution_deadline_check_returns_structured_payload(self, _run_distribution_deadline_check: object) -> None:
        with self.SessionLocal() as db:
            response = market.run_distribution_deadline_check("test-job-secret", db)

        self.assertEqual(response.funds[0].symbol, "XQQI")
        self.assertTrue(response.funds[0].alert_due)
        self.assertEqual(response.funds[0].alert_kst_date, date(2026, 4, 7))
        self.assertEqual(response.funds[0].deadline_kst_date, date(2026, 4, 8))

    @patch.object(deps.settings, "job_shared_secret", "test-job-secret")
    def test_status_current_returns_empty_state_when_no_signal_exists(self) -> None:
        with self.SessionLocal() as db:
            response = market.get_current_signal_status("test-job-secret", db)

        self.assertEqual(response.symbol, "QLD")
        self.assertIsNone(response.state)
        self.assertIsNone(response.rsi)

    @patch.object(deps.settings, "job_shared_secret", "test-job-secret")
    def test_status_history_returns_saved_alerts(self) -> None:
        with self.SessionLocal() as db:
            crud.create_signal_alert(
                db,
                symbol="QLD",
                event_type="ENTER_UNDER_30",
                state="UNDER_30",
                rsi=28.4,
                market_date=date(2026, 3, 17),
            )

        with self.SessionLocal() as db:
            response = market.get_signal_history("test-job-secret", db, limit=5)

        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].event_type, "ENTER_UNDER_30")
