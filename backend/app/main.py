from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, SessionLocal, engine, ensure_sqlite_directory, ensure_sqlite_schema
from .release_meta import load_release_meta
from .routers import apis, auth, dashboard, db_connections, jobs, logs
from .seed import bootstrap_admin, bootstrap_managed_apis


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_sqlite_directory()
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()

    with SessionLocal() as db:
        bootstrap_admin(db)
        bootstrap_managed_apis(db)

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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Job-Secret"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)
app.include_router(apis.router, prefix=settings.api_prefix)
app.include_router(db_connections.router, prefix=settings.api_prefix)
app.include_router(logs.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str | bool | None]:
    meta, error = load_release_meta()

    payload: dict[str, str | bool | None] = {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "status": "ok",
        "git_sha": None,
        "release_id": None,
        "built_at": None,
        "backend_slot": None,
        "missing_release_meta": False,
        "release_meta_error": None,
    }

    if meta:
        payload.update(meta)
        return payload

    payload["status"] = "degraded"
    payload["missing_release_meta"] = True
    payload["release_meta_error"] = error
    return payload
