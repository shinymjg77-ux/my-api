from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .database import Base, engine, ensure_sqlite_directory
from .routers import market


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_sqlite_directory()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(market.router, prefix=settings.api_prefix)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
