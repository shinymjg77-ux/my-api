import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from services.market_api.app import crud, models
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


XQQI_HTML = """
<html>
  <body>
    <table>
      <thead>
        <tr>
          <th>Declaration Date</th>
          <th>Ex-Div Date</th>
          <th>Record Date</th>
          <th>Payable Date</th>
          <th>Amount ($)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>03/03/2026</td>
          <td>03/04/2026</td>
          <td>03/04/2026</td>
          <td>03/06/2026</td>
          <td>$0.8139</td>
        </tr>
        <tr>
          <td>04/07/2026</td>
          <td>04/08/2026</td>
          <td>04/08/2026</td>
          <td>04/10/2026</td>
          <td></td>
        </tr>
        <tr>
          <td>05/05/2026</td>
          <td>05/06/2026</td>
          <td>05/06/2026</td>
          <td>05/08/2026</td>
          <td>$0.8021</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""

QQQI_HTML = """
<html>
  <body>
    <table>
      <thead>
        <tr>
          <th>Declaration Date</th>
          <th>Ex-Div Date</th>
          <th>Record Date</th>
          <th>Payable Date</th>
          <th>Amount ($)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>01/20/2026</td>
          <td>01/21/2026</td>
          <td>01/21/2026</td>
          <td>01/23/2026</td>
          <td>$0.6359</td>
        </tr>
        <tr>
          <td>03/17/2026</td>
          <td>03/18/2026</td>
          <td>03/18/2026</td>
          <td>03/20/2026</td>
          <td>$0.6089</td>
        </tr>
        <tr>
          <td>04/21/2026</td>
          <td>04/22/2026</td>
          <td>04/22/2026</td>
          <td>04/24/2026</td>
          <td></td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""

CBOE_HTML = """
<html>
  <body>
    <h3>2026<!-- --> Equities Holiday Schedule</h3>
    <table>
      <tbody>
        <tr><td>New Year's Day</td><td>January 1</td></tr>
        <tr><td>Martin Luther King, Jr. Day</td><td>January 19</td></tr>
        <tr><td>Presidents' Day</td><td>February 16</td></tr>
        <tr><td>Good Friday</td><td>April 3</td></tr>
        <tr><td>Memorial Day</td><td>May 25</td></tr>
        <tr><td>Juneteenth Holiday</td><td>June 19</td></tr>
        <tr><td>Independence Day Observed</td><td>July 3</td></tr>
        <tr><td>Labor Day</td><td>September 7</td></tr>
        <tr><td>Thanksgiving Day</td><td>November 26</td></tr>
        <tr><td>Thanksgiving Early Close</td><td>November 27</td></tr>
        <tr><td>Christmas Early Close</td><td>December 24</td></tr>
        <tr><td>Christmas Day</td><td>December 25</td></tr>
      </tbody>
    </table>
  </body>
</html>
"""


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
        market_service._load_cboe_holiday_calendar.cache_clear()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        market_service._load_cboe_holiday_calendar.cache_clear()

    def _fake_fetch_text(self, url: str) -> str:
        if url == market_service.CBOE_HOURS_URL:
            return CBOE_HTML
        if url == market_service.NEOS_DISTRIBUTION_PAGES["XQQI"]:
            return XQQI_HTML
        if url == market_service.NEOS_DISTRIBUTION_PAGES["QQQI"]:
            return QQQI_HTML
        raise AssertionError(f"Unexpected URL: {url}")

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

    @patch("services.market_api.app.services.market_service._fetch_text")
    def test_distribution_snapshot_converts_deadline_session_to_kst(self, fetch_text: object) -> None:
        fetch_text.side_effect = self._fake_fetch_text

        snapshot = market_service._next_distribution_snapshot(
            "XQQI",
            now_utc=datetime(2026, 4, 6, 20, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(snapshot.ex_dividend_date, date(2026, 4, 8))
        self.assertEqual(snapshot.alert_kst_date, date(2026, 4, 7))
        self.assertEqual(snapshot.deadline_kst_date, date(2026, 4, 8))
        self.assertEqual(snapshot.eligible_session_start_kst.isoformat(), "2026-04-07T22:30:00+09:00")
        self.assertEqual(snapshot.eligible_session_end_kst.isoformat(), "2026-04-08T05:00:00+09:00")
        self.assertTrue(snapshot.is_alert_day_kst)
        self.assertFalse(snapshot.is_deadline_day_kst)
        self.assertIsNone(snapshot.distribution_amount)

    @patch("services.market_api.app.services.market_service._fetch_text")
    def test_distribution_snapshot_handles_standard_time_session(self, fetch_text: object) -> None:
        fetch_text.side_effect = self._fake_fetch_text

        snapshot = market_service._next_distribution_snapshot(
            "QQQI",
            now_utc=datetime(2026, 1, 19, 20, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(snapshot.ex_dividend_date, date(2026, 1, 21))
        self.assertEqual(snapshot.alert_kst_date, date(2026, 1, 20))
        self.assertEqual(snapshot.eligible_session_start_kst.isoformat(), "2026-01-20T23:30:00+09:00")
        self.assertEqual(snapshot.eligible_session_end_kst.isoformat(), "2026-01-21T06:00:00+09:00")
        self.assertEqual(snapshot.distribution_amount, 0.6359)
        self.assertTrue(snapshot.is_alert_day_kst)
        self.assertFalse(snapshot.is_deadline_day_kst)

    @patch.object(market_service.settings, "market_distribution_symbols", "XQQI,QQQI")
    @patch("services.market_api.app.services.market_service._fetch_text")
    def test_distribution_deadline_check_sends_alert_once_per_symbol(self, fetch_text: object) -> None:
        fetch_text.side_effect = self._fake_fetch_text
        now_utc = datetime(2026, 4, 6, 20, 30, tzinfo=timezone.utc)

        first = market_service.run_distribution_deadline_check(self.db, now_utc=now_utc)
        second = market_service.run_distribution_deadline_check(self.db, now_utc=now_utc)

        funds_first = {item.symbol: item for item in first.funds}
        funds_second = {item.symbol: item for item in second.funds}

        self.assertTrue(funds_first["XQQI"].alert_due)
        self.assertFalse(funds_first["QQQI"].alert_due)
        self.assertFalse(funds_second["XQQI"].alert_due)
        self.assertFalse(funds_second["QQQI"].alert_due)

        alerts = list(self.db.scalars(select(models.DistributionDeadlineAlert)).all())
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].symbol, "XQQI")

        state = crud.get_distribution_deadline_state_by_symbol(self.db, "XQQI")
        self.assertIsNotNone(state)
        self.assertEqual(state.alert_kst_date, date(2026, 4, 7))
        self.assertEqual(state.deadline_kst_date, date(2026, 4, 8))

    @patch.object(market_service.settings, "market_distribution_symbols", "XQQI,QQQI")
    @patch("services.market_api.app.services.market_service._fetch_text")
    def test_distribution_deadline_check_does_not_alert_on_kst_deadline_morning(self, fetch_text: object) -> None:
        fetch_text.side_effect = self._fake_fetch_text

        result = market_service.run_distribution_deadline_check(
            self.db,
            now_utc=datetime(2026, 4, 7, 20, 30, tzinfo=timezone.utc),
        )

        funds = {item.symbol: item for item in result.funds}

        self.assertFalse(funds["XQQI"].is_alert_day_kst)
        self.assertEqual(funds["XQQI"].ex_dividend_date, date(2026, 5, 6))
        self.assertFalse(funds["XQQI"].is_deadline_day_kst)
        self.assertFalse(funds["XQQI"].alert_due)
