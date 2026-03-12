from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, SessionLocal, engine, ensure_sqlite_directory
from .routers import apis, auth, dashboard, db_connections, logs
from .seed import bootstrap_admin


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_sqlite_directory()
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        bootstrap_admin(db)

    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)
app.include_router(apis.router, prefix=settings.api_prefix)
app.include_router(db_connections.router, prefix=settings.api_prefix)
app.include_router(logs.router, prefix=settings.api_prefix)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
