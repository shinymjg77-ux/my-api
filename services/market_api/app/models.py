from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SignalState(Base):
    __tablename__ = "signal_states"
    __table_args__ = (UniqueConstraint("symbol", name="uq_signal_states_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rsi: Mapped[float] = mapped_column(Float, nullable=False)
    market_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class SignalAlert(Base):
    __tablename__ = "signal_alerts"
    __table_args__ = (
        Index("ix_signal_alerts_symbol_created_at", "symbol", "created_at"),
        Index("ix_signal_alerts_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    rsi: Mapped[float] = mapped_column(Float, nullable=False)
    market_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
