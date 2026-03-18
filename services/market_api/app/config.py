from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = SERVICE_ROOT / "data" / "app.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(SERVICE_ROOT / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Market Signal API"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    job_shared_secret: str = Field("change-me-job-secret", min_length=16)
    database_url: str = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

    market_rsi_symbol: str = "QLD"
    market_rsi_period: int = 14
    market_rsi_threshold: float = 30.0
    market_briefing_symbols: str = "^GSPC,^IXIC"

    @field_validator("market_briefing_symbols", mode="before")
    @classmethod
    def normalize_symbols(cls, value: str) -> str:
        return ",".join(item.strip() for item in value.split(",") if item.strip())

    @property
    def market_briefing_symbols_list(self) -> list[str]:
        return [item.strip() for item in self.market_briefing_symbols.split(",") if item.strip()]


settings = Settings()
