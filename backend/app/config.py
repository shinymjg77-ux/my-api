import json
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "app.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Personal API Admin"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    secret_key: str = Field(..., min_length=32)
    encryption_key: str = Field(..., min_length=44)
    job_shared_secret: str = Field(..., min_length=32)
    access_token_expire_minutes: int = 120
    admin_cookie_name: str = "admin_session"
    cookie_secure: bool = True
    cookie_samesite: str = "lax"

    database_url: str = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    cors_origins: list[str] = ["http://localhost:3000"]

    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None

    dashboard_window_days: int = 7
    log_page_size_default: int = 20
    log_page_size_max: int = 100
    managed_api_admin_base_url: str = "http://127.0.0.1:8000"
    managed_api_market_base_url: str = "http://127.0.0.1:8100"
    ops_systemd_units: str = (
        "personal-api-admin-backend.service,"
        "personal-api-admin-frontend.service,"
        "personal-market-api.service,"
        "nginx.service"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        normalized = value.strip()
        if normalized.startswith("["):
            parsed = json.loads(normalized)
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise ValueError("CORS_ORIGINS JSON payload must be a list of strings")
            return [item.strip() for item in parsed if item.strip()]
        return [item.strip() for item in normalized.split(",") if item.strip()]

    @field_validator("managed_api_admin_base_url", "managed_api_market_base_url")
    @classmethod
    def normalize_managed_api_base_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @property
    def ops_systemd_units_list(self) -> list[str]:
        return [item.strip() for item in self.ops_systemd_units.split(",") if item.strip()]


settings = Settings()
