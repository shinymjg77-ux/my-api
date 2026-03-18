import os
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from services.market_api.app import crud
from services.market_api.app.database import Base
from services.market_api.app.services import market_service


def make_chart_payload(closes: list[float]) -> dict:
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [1740787200 + index * 86400 for index in range(len(closes))],
                    "indicators": {
                        "quote": [
                            {
                                "close": closes,
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


class MarketServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        self.engine = create_engine(
            f"sqlite:///{handle.name}",
            connect_args={"check_same_thread": False},
            future=True,
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_calculate_rsi_requires_period_plus_one_closes(self) -> None:
        with self.assertRaises(ValueError):
            market_service._calculate_rsi([1.0] * 14, 14)

    def test_state_threshold_is_inclusive(self) -> None:
        self.assertEqual(market_service._state_for_rsi(30.0, 30.0), "UNDER_30")
        self.assertEqual(market_service._state_for_rsi(30.1, 30.0), "ABOVE_30")

    def test_event_transition_mapping(self) -> None:
        self.assertEqual(market_service._event_for_transition("ABOVE_30", "UNDER_30"), "ENTER_UNDER_30")
        self.assertEqual(market_service._event_for_transition("UNDER_30", "ABOVE_30"), "EXIT_UNDER_30")
        self.assertIsNone(market_service._event_for_transition(None, "UNDER_30"))

    @patch.object(market_service.settings, "market_rsi_symbol", "QLD")
    @patch.object(market_service.settings, "market_rsi_threshold", 30.0)
    @patch.object(market_service.settings, "market_rsi_period", 14)
    @patch("services.market_api.app.services.market_service._fetch_chart_payload")
    def test_rsi_check_first_run_stores_state_without_alert(self, fetch_chart_payload: object) -> None:
        fetch_chart_payload.return_value = make_chart_payload(
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]
        )

        response = market_service.run_rsi_check(self.db)

        self.assertEqual(response.close, 114.0)
        self.assertEqual(response.change, 1.0)
        self.assertEqual(response.change_pct, 0.88)
        self.assertEqual(response.previous_rsi, 100.0)
        self.assertEqual(response.rsi_change, 0.0)
        self.assertEqual(response.state, "ABOVE_30")
        self.assertFalse(response.changed)
        self.assertIsNone(response.event)
        alerts, total = crud.list_signal_alerts(self.db, symbol="QLD")
        self.assertEqual(total, 0)
        self.assertEqual(alerts, [])

    @patch.object(market_service.settings, "market_rsi_symbol", "QLD")
    @patch.object(market_service.settings, "market_rsi_threshold", 30.0)
    @patch.object(market_service.settings, "market_rsi_period", 14)
    @patch("services.market_api.app.services.market_service._fetch_chart_payload")
    def test_rsi_check_creates_enter_under_30_alert_on_transition(self, fetch_chart_payload: object) -> None:
        fetch_chart_payload.side_effect = [
            make_chart_payload([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]),
            make_chart_payload([114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]),
        ]

        market_service.run_rsi_check(self.db)
        response = market_service.run_rsi_check(self.db)

        self.assertEqual(response.close, 100.0)
        self.assertEqual(response.change, -1.0)
        self.assertEqual(response.change_pct, -0.99)
        self.assertEqual(response.previous_rsi, 0.0)
        self.assertEqual(response.rsi_change, 0.0)
        self.assertEqual(response.previous_state, "ABOVE_30")
        self.assertEqual(response.state, "UNDER_30")
        self.assertEqual(response.event, "ENTER_UNDER_30")

    @patch.object(market_service.settings, "market_rsi_period", 14)
    @patch.object(market_service.settings, "market_rsi_threshold", 30.0)
    @patch("services.market_api.app.services.market_service._fetch_chart_payload")
    def test_morning_briefing_uses_latest_completed_closes(self, fetch_chart_payload: object) -> None:
        fetch_chart_payload.side_effect = [
            make_chart_payload([5000.0, 5050.0]),
            make_chart_payload([16000.0, 15880.0]),
        ]

        response = market_service.get_morning_briefing()

        self.assertEqual(response.indices.sp500.symbol, "^GSPC")
        self.assertEqual(response.indices.sp500.change_pct, 1.0)
        self.assertEqual(response.indices.nasdaq.symbol, "^IXIC")
        self.assertEqual(response.indices.nasdaq.change_pct, -0.75)

    @patch.object(market_service.settings, "market_rsi_symbol", "QLD")
    @patch.object(market_service.settings, "market_rsi_threshold", 30.0)
    @patch.object(market_service.settings, "market_rsi_period", 14)
    @patch("services.market_api.app.services.market_service._fetch_chart_payload")
    def test_rsi_check_reuses_saved_state(self, fetch_chart_payload: object) -> None:
        fetch_chart_payload.side_effect = [
            make_chart_payload([114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]),
            make_chart_payload([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]),
        ]

        first = market_service.run_rsi_check(self.db)
        second = market_service.run_rsi_check(self.db)

        self.assertEqual(first.close, 100.0)
        self.assertEqual(first.change, -1.0)
        self.assertEqual(first.change_pct, -0.99)
        self.assertEqual(first.previous_rsi, 0.0)
        self.assertEqual(first.rsi_change, 0.0)
        self.assertEqual(second.close, 114.0)
        self.assertEqual(second.change, 1.0)
        self.assertEqual(second.change_pct, 0.88)
        self.assertEqual(second.previous_rsi, 100.0)
        self.assertEqual(second.rsi_change, 0.0)
        self.assertEqual(first.state, "UNDER_30")
        self.assertEqual(second.previous_state, "UNDER_30")
        self.assertEqual(second.event, "EXIT_UNDER_30")

        state = crud.get_signal_state_by_symbol(self.db, "QLD")
        self.assertIsNotNone(state)
        self.assertEqual(state.market_date, date(2025, 3, 15))
