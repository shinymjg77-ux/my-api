from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def ensure_sqlite_directory() -> None:
    if not _is_sqlite(settings.database_url):
        return

    raw_path = settings.database_url.replace("sqlite:///", "", 1)
    db_path = Path(raw_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)


def ensure_sqlite_schema() -> None:
    if not _is_sqlite(settings.database_url):
        return

    with engine.begin() as connection:
        table_names = {
            row[0]
            for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }

        state_table = "distribution_deadline_states"
        if state_table in table_names:
            state_columns = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info('{state_table}')"))
            }
            if "alert_kst_date" not in state_columns:
                connection.execute(text(f"ALTER TABLE {state_table} ADD COLUMN alert_kst_date DATE"))
                connection.execute(
                    text(
                        f"UPDATE {state_table} "
                        "SET alert_kst_date = deadline_kst_date "
                        "WHERE alert_kst_date IS NULL"
                    )
                )

        alert_table = "distribution_deadline_alerts"
        if alert_table in table_names:
            alert_columns = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info('{alert_table}')"))
            }
            if "alert_kst_date" not in alert_columns:
                connection.execute(text(f"ALTER TABLE {alert_table} ADD COLUMN alert_kst_date DATE"))
                connection.execute(
                    text(
                        f"UPDATE {alert_table} "
                        "SET alert_kst_date = deadline_kst_date "
                        "WHERE alert_kst_date IS NULL"
                    )
                )


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite(settings.database_url) else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
