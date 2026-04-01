from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas


def get_signal_state_by_symbol(db: Session, symbol: str) -> models.SignalState | None:
    return db.scalar(select(models.SignalState).where(models.SignalState.symbol == symbol))


def upsert_signal_state(
    db: Session,
    *,
    symbol: str,
    state: schemas.MarketSignalState,
    previous_state: schemas.MarketSignalState | None,
    rsi: float,
    market_date: date,
    checked_at: datetime,
) -> models.SignalState:
    item = get_signal_state_by_symbol(db, symbol)
    if item is None:
        item = models.SignalState(
            symbol=symbol,
            state=state,
            previous_state=previous_state,
            rsi=rsi,
            market_date=market_date,
            last_checked_at=checked_at,
        )
    else:
        item.state = state
        item.previous_state = previous_state
        item.rsi = rsi
        item.market_date = market_date
        item.last_checked_at = checked_at

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_signal_alert(
    db: Session,
    *,
    symbol: str,
    event_type: schemas.MarketSignalEventType,
    state: schemas.MarketSignalState,
    rsi: float,
    market_date: date,
) -> models.SignalAlert:
    item = models.SignalAlert(
        symbol=symbol,
        event_type=event_type,
        state=state,
        rsi=rsi,
        market_date=market_date,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_signal_alerts(
    db: Session,
    *,
    symbol: str | None = None,
    limit: int = 20,
) -> tuple[list[models.SignalAlert], int]:
    stmt = select(models.SignalAlert).order_by(models.SignalAlert.created_at.desc())
    count_stmt = select(func.count(models.SignalAlert.id))

    if symbol:
        stmt = stmt.where(models.SignalAlert.symbol == symbol)
        count_stmt = count_stmt.where(models.SignalAlert.symbol == symbol)

    items = list(db.scalars(stmt.limit(limit)).all())
    total = db.scalar(count_stmt) or 0
    return items, total


def get_distribution_deadline_state_by_symbol(db: Session, symbol: str) -> models.DistributionDeadlineState | None:
    return db.scalar(select(models.DistributionDeadlineState).where(models.DistributionDeadlineState.symbol == symbol))


def upsert_distribution_deadline_state(
    db: Session,
    *,
    symbol: str,
    ex_dividend_date: date,
    alert_kst_date: date,
    deadline_kst_date: date,
    checked_at: datetime,
    last_alert_key: str | None,
) -> models.DistributionDeadlineState:
    item = get_distribution_deadline_state_by_symbol(db, symbol)
    if item is None:
        item = models.DistributionDeadlineState(
            symbol=symbol,
            ex_dividend_date=ex_dividend_date,
            alert_kst_date=alert_kst_date,
            deadline_kst_date=deadline_kst_date,
            last_alert_key=last_alert_key,
            last_checked_at=checked_at,
        )
    else:
        item.ex_dividend_date = ex_dividend_date
        item.alert_kst_date = alert_kst_date
        item.deadline_kst_date = deadline_kst_date
        item.last_alert_key = last_alert_key
        item.last_checked_at = checked_at

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_distribution_deadline_alert(
    db: Session,
    *,
    symbol: str,
    ex_dividend_date: date,
    alert_kst_date: date,
    deadline_kst_date: date,
    distribution_amount: float | None,
) -> models.DistributionDeadlineAlert:
    item = models.DistributionDeadlineAlert(
        symbol=symbol,
        ex_dividend_date=ex_dividend_date,
        alert_kst_date=alert_kst_date,
        deadline_kst_date=deadline_kst_date,
        distribution_amount=distribution_amount,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
