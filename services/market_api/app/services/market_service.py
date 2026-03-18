import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from .. import crud, schemas
from ..config import settings


YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
BRIEFING_SYMBOL_KEYS = {
    "^GSPC": ("sp500", "S&P 500"),
    "^IXIC": ("nasdaq", "Nasdaq Composite"),
}


class MarketDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class DailyClosePoint:
    market_date: date
    close: float


def get_signal_symbol() -> str:
    return settings.market_rsi_symbol.strip().upper()


def get_rsi_threshold() -> float:
    return settings.market_rsi_threshold


def _fetch_chart_payload(symbol: str, *, range_value: str, interval: str = "1d") -> dict:
    query = urlencode({"range": range_value, "interval": interval, "includePrePost": "false"})
    url = f"{YAHOO_CHART_BASE_URL}{quote(symbol, safe='')}?{query}"
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
        raise MarketDataError(f"Failed to fetch market data for {symbol}") from exc


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
