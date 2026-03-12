from time import perf_counter

from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from ..schemas import DBConnectionTestRequest


def _build_test_url(payload: DBConnectionTestRequest) -> str | URL:
    if payload.db_type == "sqlite":
        if not payload.db_name:
            raise ValueError("SQLite test requires db_name. Use a file path such as ./data/external.db")
        return f"sqlite:///{payload.db_name}"

    if payload.db_type == "postgresql":
        if not all([payload.host, payload.port, payload.db_name, payload.username]):
            raise ValueError("PostgreSQL test requires host, port, db_name, and username")
        return URL.create(
            "postgresql+psycopg",
            username=payload.username,
            password=payload.password or "",
            host=payload.host,
            port=payload.port,
            database=payload.db_name,
        )

    raise ValueError(f"Unsupported db_type: {payload.db_type}")


def test_database_connection(payload: DBConnectionTestRequest) -> tuple[bool, str, int | None]:
    url = _build_test_url(payload)
    connect_args = {"check_same_thread": False} if payload.db_type == "sqlite" else {"connect_timeout": 5}

    started = perf_counter()
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args, future=True)

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        latency_ms = int((perf_counter() - started) * 1000)
        return True, "Connection succeeded", latency_ms
    except (SQLAlchemyError, OSError, ValueError) as exc:
        return False, str(exc), None
    finally:
        engine.dispose()
