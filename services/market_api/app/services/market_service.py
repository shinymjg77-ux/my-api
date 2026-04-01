import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from html import unescape
from typing import Literal
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .. import crud, schemas
from ..config import settings


YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
CBOE_HOURS_URL = "https://www.cboe.com/about/hours"
BRIEFING_SYMBOL_KEYS = {
    "^GSPC": ("sp500", "S&P 500"),
    "^IXIC": ("nasdaq", "Nasdaq Composite"),
}
NEOS_DISTRIBUTION_PAGES = {
    "QQQI": "https://neosfunds.com/qqqi/",
    "XQQI": "https://neosfunds.com/xqqi/",
}
EARLY_CLOSE_HOLIDAYS = {
    "Thanksgiving Early Close",
    "Christmas Early Close",
}
EASTERN_TZ = ZoneInfo("America/New_York")
KST_TZ = ZoneInfo("Asia/Seoul")


class MarketDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class DailyClosePoint:
    market_date: date
    close: float


@dataclass(frozen=True)
class DistributionScheduleRow:
    symbol: str
    source_url: str
    declaration_date: date
    ex_dividend_date: date
    record_date: date
    payable_date: date
    distribution_amount: float | None


@dataclass(frozen=True)
class TradingSessionWindow:
    start_et: datetime
    end_et: datetime
    start_kst: datetime
    end_kst: datetime


def get_signal_symbol() -> str:
    return settings.market_rsi_symbol.strip().upper()


def get_rsi_threshold() -> float:
    return settings.market_rsi_threshold


def get_distribution_symbols() -> list[str]:
    symbols = settings.market_distribution_symbols_list
    if not symbols:
        raise MarketDataError("MARKET_DISTRIBUTION_SYMBOLS must not be empty")
    unsupported = [symbol for symbol in symbols if symbol not in NEOS_DISTRIBUTION_PAGES]
    if unsupported:
        raise MarketDataError(f"Unsupported distribution symbols: {', '.join(unsupported)}")
    return symbols


def _fetch_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    except Exception as exc:  # pragma: no cover
        raise MarketDataError(f"Failed to fetch JSON from {url}") from exc


def _fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Mozilla/5.0",
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", "ignore")
    except Exception as exc:  # pragma: no cover
        raise MarketDataError(f"Failed to fetch HTML from {url}") from exc


def _fetch_chart_payload(symbol: str, *, range_value: str, interval: str = "1d") -> dict:
    query = urlencode({"range": range_value, "interval": interval, "includePrePost": "false"})
    url = f"{YAHOO_CHART_BASE_URL}{quote(symbol, safe='')}?{query}"
    return _fetch_json(url)


def _extract_chart_result(payload: dict) -> dict:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise MarketDataError(str(chart["error"]))

    results = chart.get("result") or []
    if not results:
        raise MarketDataError("Yahoo Finance returned no chart result")
    return results[0]


def _parse_daily_closes(payload: dict) -> list[DailyClosePoint]:
    result = _extract_chart_result(payload)
    timestamps = result.get("timestamp") or []
    quote_entries = (result.get("indicators") or {}).get("quote") or []
    closes = (quote_entries[0] if quote_entries else {}).get("close") or []

    if not timestamps or not closes:
        raise MarketDataError("Yahoo Finance returned no closing prices")

    by_date: dict[date, float] = {}
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        market_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        by_date[market_date] = float(close)

    if len(by_date) < 2:
        raise MarketDataError("Insufficient daily closing prices")

    return [DailyClosePoint(market_date=item_date, close=close) for item_date, close in sorted(by_date.items())]


def _calculate_rsi(closes: list[float], period: int) -> float:
    if len(closes) < period + 1:
        raise ValueError("At least period + 1 closes are required to compute RSI")

    deltas = [current - previous for previous, current in zip(closes, closes[1:])]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [abs(min(delta, 0.0)) for delta in deltas]

    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period

    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    if average_gain == 0:
        return 0.0

    relative_strength = average_gain / average_loss
    return round(100 - (100 / (1 + relative_strength)), 2)


def _state_for_rsi(value: float, threshold: float) -> schemas.MarketSignalState:
    return "UNDER_30" if value <= threshold else "ABOVE_30"


def _event_for_transition(
    previous_state: schemas.MarketSignalState | None,
    current_state: schemas.MarketSignalState,
) -> schemas.MarketSignalEventType | None:
    transitions: dict[
        tuple[schemas.MarketSignalState, schemas.MarketSignalState],
        schemas.MarketSignalEventType,
    ] = {
        ("ABOVE_30", "UNDER_30"): "ENTER_UNDER_30",
        ("UNDER_30", "ABOVE_30"): "EXIT_UNDER_30",
    }
    if previous_state is None:
        return None
    return transitions.get((previous_state, current_state))


def _build_index_snapshot(symbol: str, points: list[DailyClosePoint]) -> schemas.MarketIndexSnapshotResponse:
    previous_point = points[-2]
    latest_point = points[-1]
    change = round(latest_point.close - previous_point.close, 2)
    change_pct = round((change / previous_point.close) * 100, 2) if previous_point.close else 0.0
    _, name = BRIEFING_SYMBOL_KEYS[symbol]

    return schemas.MarketIndexSnapshotResponse(
        symbol=symbol,
        name=name,
        market_date=latest_point.market_date,
        close=round(latest_point.close, 2),
        change=change,
        change_pct=change_pct,
    )


def _briefing_symbols() -> dict[Literal["sp500", "nasdaq"], str]:
    symbols = {symbol.strip().upper() for symbol in settings.market_briefing_symbols_list}
    required = set(BRIEFING_SYMBOL_KEYS)
    if not required.issubset(symbols):
        raise MarketDataError("MARKET_BRIEFING_SYMBOLS must include ^GSPC and ^IXIC")

    return {"sp500": "^GSPC", "nasdaq": "^IXIC"}


def _strip_html(value: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", value)).strip()


def _parse_mmddyyyy(value: str) -> date:
    return datetime.strptime(value, "%m/%d/%Y").date()


def _parse_distribution_rows(symbol: str) -> list[DistributionScheduleRow]:
    url = NEOS_DISTRIBUTION_PAGES[symbol]
    html = _fetch_text(url)
    rows: list[DistributionScheduleRow] = []
    for match in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", match.group(1), re.S)
        if len(cells) != 5:
            continue
        values = [_strip_html(cell) for cell in cells]
        if not all(re.fullmatch(r"\d{2}/\d{2}/\d{4}", value) for value in values[:4]):
            continue
        amount_text = values[4].replace("$", "").replace(",", "").strip()
        rows.append(
            DistributionScheduleRow(
                symbol=symbol,
                source_url=url,
                declaration_date=_parse_mmddyyyy(values[0]),
                ex_dividend_date=_parse_mmddyyyy(values[1]),
                record_date=_parse_mmddyyyy(values[2]),
                payable_date=_parse_mmddyyyy(values[3]),
                distribution_amount=float(amount_text) if amount_text else None,
            )
        )

    if not rows:
        raise MarketDataError(f"Failed to parse distribution rows for {symbol}")
    return sorted(rows, key=lambda item: item.ex_dividend_date)


def _extract_cboe_holiday_rows(html: str, year: int) -> list[tuple[str, str]]:
    heading_index = html.find(f"{year}<!-- --> Equities Holiday Schedule")
    if heading_index < 0:
        heading_index = html.find(f"{year} Equities Holiday Schedule")
    if heading_index < 0:
        raise MarketDataError(f"Failed to find Cboe holiday schedule for {year}")

    tbody_index = html.find("<tbody", heading_index)
    if tbody_index < 0:
        raise MarketDataError(f"Failed to find Cboe holiday table for {year}")
    tbody_open_end = html.find(">", tbody_index)
    tbody_close = html.find("</tbody>", tbody_open_end)
    if tbody_open_end < 0 or tbody_close < 0:
        raise MarketDataError(f"Failed to parse Cboe holiday table for {year}")
    tbody_html = html[tbody_open_end + 1 : tbody_close]

    rows: list[tuple[str, str]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_html, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        if len(cells) != 2:
            continue
        rows.append((_strip_html(cells[0]), _strip_html(cells[1])))
    if not rows:
        raise MarketDataError(f"Failed to parse Cboe holiday rows for {year}")
    return rows


def _parse_month_day(value: str, year: int) -> date:
    return datetime.strptime(f"{value} {year}", "%B %d %Y").date()


@lru_cache(maxsize=8)
def _load_cboe_holiday_calendar(year: int) -> tuple[set[date], set[date]]:
    html = _fetch_text(CBOE_HOURS_URL)
    full_holidays: set[date] = set()
    early_closes: set[date] = set()

    for name, raw_date in _extract_cboe_holiday_rows(html, year):
        holiday_date = _parse_month_day(raw_date, year)
        if name in EARLY_CLOSE_HOLIDAYS:
            early_closes.add(holiday_date)
        else:
            full_holidays.add(holiday_date)

    return full_holidays, early_closes


def _previous_us_equities_trading_day(target_date: date) -> date:
    full_holidays, _ = _load_cboe_holiday_calendar(target_date.year)
    candidate = target_date - timedelta(days=1)
    while candidate.weekday() >= 5 or candidate in full_holidays:
        candidate -= timedelta(days=1)
    return candidate


def _build_us_equities_session(trading_day: date) -> TradingSessionWindow:
    _, early_closes = _load_cboe_holiday_calendar(trading_day.year)
    start_et = datetime.combine(trading_day, time(hour=9, minute=30), tzinfo=EASTERN_TZ)
    close_hour = 13 if trading_day in early_closes else 16
    end_et = datetime.combine(trading_day, time(hour=close_hour, minute=0), tzinfo=EASTERN_TZ)
    return TradingSessionWindow(
        start_et=start_et,
        end_et=end_et,
        start_kst=start_et.astimezone(KST_TZ),
        end_kst=end_et.astimezone(KST_TZ),
    )


def _next_distribution_snapshot(
    symbol: str,
    *,
    now_utc: datetime,
) -> schemas.DistributionDeadlineFundResponse:
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_kst = now_utc.astimezone(KST_TZ)

    candidates: list[schemas.DistributionDeadlineFundResponse] = []
    for row in _parse_distribution_rows(symbol):
        if row.ex_dividend_date < now_kst.date():
            continue
        trading_day = _previous_us_equities_trading_day(row.ex_dividend_date)
        session = _build_us_equities_session(trading_day)
        alert_kst_date = session.start_kst.date()
        deadline_kst_date = session.end_kst.date()
        if alert_kst_date < now_kst.date():
            continue
        candidates.append(
            schemas.DistributionDeadlineFundResponse(
                symbol=row.symbol,
                source_url=row.source_url,
                declaration_date=row.declaration_date,
                ex_dividend_date=row.ex_dividend_date,
                record_date=row.record_date,
                payable_date=row.payable_date,
                distribution_amount=row.distribution_amount,
                eligible_session_start_et=session.start_et,
                eligible_session_end_et=session.end_et,
                eligible_session_start_kst=session.start_kst,
                eligible_session_end_kst=session.end_kst,
                alert_kst_date=alert_kst_date,
                is_alert_day_kst=now_kst.date() == alert_kst_date,
                deadline_kst_date=deadline_kst_date,
                is_deadline_day_kst=now_kst.date() == deadline_kst_date,
                alert_due=False,
            )
        )

    if not candidates:
        raise MarketDataError(f"No upcoming distribution deadline found for {symbol}")
    return min(candidates, key=lambda item: (item.ex_dividend_date, item.deadline_kst_date))


def get_morning_briefing() -> schemas.MorningBriefingResponse:
    symbol_map = _briefing_symbols()
    sp500 = _build_index_snapshot(
        symbol_map["sp500"],
        _parse_daily_closes(_fetch_chart_payload(symbol_map["sp500"], range_value="1mo")),
    )
    nasdaq = _build_index_snapshot(
        symbol_map["nasdaq"],
        _parse_daily_closes(_fetch_chart_payload(symbol_map["nasdaq"], range_value="1mo")),
    )

    return schemas.MorningBriefingResponse(
        market_date=max(sp500.market_date, nasdaq.market_date),
        generated_at=datetime.now(timezone.utc),
        indices=schemas.MorningBriefingIndicesResponse(sp500=sp500, nasdaq=nasdaq),
    )


def run_rsi_check(db: Session) -> schemas.RSICheckResponse:
    symbol = get_signal_symbol()
    points = _parse_daily_closes(_fetch_chart_payload(symbol, range_value="6mo"))
    closes = [item.close for item in points]
    rsi = _calculate_rsi(closes, settings.market_rsi_period)
    if len(closes) >= settings.market_rsi_period + 2:
        previous_rsi = _calculate_rsi(closes[:-1], settings.market_rsi_period)
    else:
        previous_rsi = rsi
    rsi_change = round(rsi - previous_rsi, 2)
    latest_point = points[-1]
    previous_point = points[-2]
    change = round(latest_point.close - previous_point.close, 2)
    change_pct = round((change / previous_point.close) * 100, 2) if previous_point.close else 0.0
    current_state = _state_for_rsi(rsi, settings.market_rsi_threshold)
    existing_state = crud.get_signal_state_by_symbol(db, symbol)
    previous_state = existing_state.state if existing_state else None
    event = _event_for_transition(previous_state, current_state)
    checked_at = datetime.now(timezone.utc)

    crud.upsert_signal_state(
        db,
        symbol=symbol,
        state=current_state,
        previous_state=previous_state,
        rsi=rsi,
        market_date=latest_point.market_date,
        checked_at=checked_at,
    )

    if event:
        crud.create_signal_alert(
            db,
            symbol=symbol,
            event_type=event,
            state=current_state,
            rsi=rsi,
            market_date=latest_point.market_date,
        )

    return schemas.RSICheckResponse(
        symbol=symbol,
        close=round(latest_point.close, 2),
        change=change,
        change_pct=change_pct,
        rsi=rsi,
        previous_rsi=previous_rsi,
        rsi_change=rsi_change,
        threshold=settings.market_rsi_threshold,
        state=current_state,
        previous_state=previous_state,
        changed=event is not None,
        event=event,
        market_date=latest_point.market_date,
        checked_at=checked_at,
    )


def run_distribution_deadline_check(
    db: Session,
    *,
    now_utc: datetime | None = None,
) -> schemas.DistributionDeadlineCheckResponse:
    checked_at = now_utc or datetime.now(timezone.utc)
    funds: list[schemas.DistributionDeadlineFundResponse] = []

    for symbol in get_distribution_symbols():
        snapshot = _next_distribution_snapshot(symbol, now_utc=checked_at)
        existing_state = crud.get_distribution_deadline_state_by_symbol(db, symbol)
        alert_key = f"{symbol}:{snapshot.ex_dividend_date.isoformat()}:{snapshot.alert_kst_date.isoformat()}"
        alert_due = snapshot.is_alert_day_kst and (
            existing_state is None or existing_state.last_alert_key != alert_key
        )
        last_alert_key = (
            alert_key if alert_due else existing_state.last_alert_key if existing_state is not None else None
        )

        crud.upsert_distribution_deadline_state(
            db,
            symbol=symbol,
            ex_dividend_date=snapshot.ex_dividend_date,
            alert_kst_date=snapshot.alert_kst_date,
            deadline_kst_date=snapshot.deadline_kst_date,
            checked_at=checked_at,
            last_alert_key=last_alert_key,
        )

        if alert_due:
            crud.create_distribution_deadline_alert(
                db,
                symbol=symbol,
                ex_dividend_date=snapshot.ex_dividend_date,
                alert_kst_date=snapshot.alert_kst_date,
                deadline_kst_date=snapshot.deadline_kst_date,
                distribution_amount=snapshot.distribution_amount,
            )

        funds.append(snapshot.model_copy(update={"alert_due": alert_due}))

    return schemas.DistributionDeadlineCheckResponse(
        generated_at=checked_at,
        funds=funds,
    )
