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
        if "managed_apis" not in table_names:
            return

        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info('managed_apis')"))
        }
        if "group_path" not in columns:
            connection.execute(text("ALTER TABLE managed_apis ADD COLUMN group_path VARCHAR(255)"))


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
