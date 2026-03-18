from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..deps import require_job_secret
from ..services import market_service


router = APIRouter(tags=["market"])


@router.get("/briefings/morning", response_model=schemas.MorningBriefingResponse)
def get_morning_briefing(
    _: str = Depends(require_job_secret),
) -> schemas.MorningBriefingResponse:
    try:
        return market_service.get_morning_briefing()
    except market_service.MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to build morning briefing") from exc


@router.post("/jobs/rsi-check", response_model=schemas.RSICheckResponse)
def run_rsi_check(
    _: str = Depends(require_job_secret),
    db: Session = Depends(get_db),
) -> schemas.RSICheckResponse:
    try:
        return market_service.run_rsi_check(db)
    except market_service.MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to calculate RSI signal") from exc


@router.get("/status/current", response_model=schemas.SignalStateCurrentResponse)
def get_current_signal_status(
    _: str = Depends(require_job_secret),
    db: Session = Depends(get_db),
) -> schemas.SignalStateCurrentResponse:
    item = crud.get_signal_state_by_symbol(db, market_service.get_signal_symbol())
    if item is None:
        return schemas.SignalStateCurrentResponse(
            symbol=market_service.get_signal_symbol(),
            threshold=market_service.get_rsi_threshold(),
            state=None,
            previous_state=None,
            rsi=None,
            market_date=None,
            last_checked_at=None,
        )

    return schemas.SignalStateCurrentResponse(
        symbol=item.symbol,
        threshold=market_service.get_rsi_threshold(),
        state=item.state,
        previous_state=item.previous_state,
        rsi=item.rsi,
        market_date=item.market_date,
        last_checked_at=item.last_checked_at,
    )


@router.get("/status/history", response_model=schemas.SignalAlertHistoryResponse)
def get_signal_history(
    _: str = Depends(require_job_secret),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> schemas.SignalAlertHistoryResponse:
    items, total = crud.list_signal_alerts(db, symbol=market_service.get_signal_symbol(), limit=limit)
    return schemas.SignalAlertHistoryResponse(
        items=[schemas.SignalAlertResponse.model_validate(item) for item in items],
        total=total,
    )
