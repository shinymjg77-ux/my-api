from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


MarketSignalState = Literal["ABOVE_30", "UNDER_30"]
MarketSignalEventType = Literal["ENTER_UNDER_30", "EXIT_UNDER_30"]
MarketDeliverySkipReason = Literal["market_closed"]


class MarketIndexSnapshotResponse(BaseModel):
    symbol: str
    name: str
    market_date: date
    close: float
    change: float
    change_pct: float


class MorningBriefingIndicesResponse(BaseModel):
    sp500: MarketIndexSnapshotResponse
    nasdaq: MarketIndexSnapshotResponse


class MorningBriefingResponse(BaseModel):
    target_session_date: date
    should_send: bool
    skip_reason: MarketDeliverySkipReason | None
    market_date: date
    generated_at: datetime
    indices: MorningBriefingIndicesResponse


class RSICheckResponse(BaseModel):
    symbol: str
    target_session_date: date
    should_send: bool
    skip_reason: MarketDeliverySkipReason | None
    close: float
    change: float
    change_pct: float
    rsi: float
    previous_rsi: float
    rsi_change: float
    threshold: float
    state: MarketSignalState
    previous_state: MarketSignalState | None
    changed: bool
    event: MarketSignalEventType | None
    market_date: date
    checked_at: datetime


class SignalStateCurrentResponse(BaseModel):
    symbol: str
    threshold: float
    state: MarketSignalState | None
    previous_state: MarketSignalState | None
    rsi: float | None
    market_date: date | None
    last_checked_at: datetime | None


class SignalAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    event_type: MarketSignalEventType
    state: MarketSignalState
    rsi: float
    market_date: date
    created_at: datetime


class SignalAlertHistoryResponse(BaseModel):
    items: list[SignalAlertResponse]
    total: int


class DistributionDeadlineFundResponse(BaseModel):
    symbol: str
    source_url: str
    declaration_date: date
    ex_dividend_date: date
    record_date: date
    payable_date: date
    distribution_amount: float | None
    eligible_session_start_et: datetime
    eligible_session_end_et: datetime
    eligible_session_start_kst: datetime
    eligible_session_end_kst: datetime
    alert_kst_date: date
    is_alert_day_kst: bool
    deadline_kst_date: date
    is_deadline_day_kst: bool
    alert_due: bool


class DistributionDeadlineCheckResponse(BaseModel):
    generated_at: datetime
    funds: list[DistributionDeadlineFundResponse]
