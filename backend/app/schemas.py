from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


HTTPMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
DBType = Literal["sqlite", "postgresql"]
LogType = Literal["auth", "api", "db", "system"]
LogLevel = Literal["info", "warning", "error"]


class MessageResponse(BaseModel):
    message: str


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminPasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("current_password", "new_password", "confirm_password")
    @classmethod
    def normalize_password(cls, value: str) -> str:
        return value.strip()


class ManagedAPIBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    url: str = Field(..., min_length=10, max_length=500)
    method: HTTPMethod
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return normalized


class ManagedAPICreate(ManagedAPIBase):
    pass


class ManagedAPIUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    url: str | None = Field(default=None, min_length=10, max_length=500)
    method: HTTPMethod | None = None
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("url")
    @classmethod
    def validate_optional_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return normalized


class ManagedAPIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    method: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DBConnectionBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    db_type: DBType
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    db_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_connection_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("host", "db_name", "username", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class DBConnectionCreate(DBConnectionBase):
    password: str | None = Field(default=None, max_length=255)


class DBConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    db_type: DBType | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    db_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class DBConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    db_type: str
    host: str | None
    port: int | None
    db_name: str | None
    username: str | None
    description: str | None
    is_active: bool
    has_password: bool
    password_masked: str
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_message: str | None
    created_at: datetime
    updated_at: datetime


class DBConnectionTestRequest(BaseModel):
    db_type: DBType
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    db_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)


class DBConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int | None = None


class ActivityLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    log_type: str
    api_id: int | None
    api_name: str | None = None
    db_connection_id: int | None
    db_connection_name: str | None = None
    level: str
    status_code: int | None
    is_success: bool
    message: str
    detail: str | None
    created_at: datetime


class ActivityLogListResponse(BaseModel):
    items: list[ActivityLogResponse]
    total: int
    page: int
    page_size: int


class DashboardSummaryResponse(BaseModel):
    recent_success_count: int
    recent_failure_count: int
    api_count: int
    db_connection_count: int
    recent_error_logs: list[ActivityLogResponse]


class OpsServiceStatusResponse(BaseModel):
    name: str
    description: str
    active_state: str
    sub_state: str
    is_healthy: bool


class OpsProcessStatusResponse(BaseModel):
    name: str
    status: str
    is_healthy: bool
    attention_level: Literal["healthy", "warning", "critical"]
    group_key: str
    group_label: str
    pid: int | None
    restart_count: int
    cpu_percent: float
    memory_bytes: int
    uptime_seconds: int | None
    cwd: str | None


class HostCpuMetricsResponse(BaseModel):
    usage_percent: float | None
    status: Literal["healthy", "warning", "critical", "unavailable"]


class HostMemoryMetricsResponse(BaseModel):
    total_bytes: int | None
    used_bytes: int | None
    available_bytes: int | None
    usage_percent: float | None
    status: Literal["healthy", "warning", "critical", "unavailable"]


class HostDiskMetricsResponse(BaseModel):
    mount_path: str
    total_bytes: int | None
    used_bytes: int | None
    free_bytes: int | None
    usage_percent: float | None
    status: Literal["healthy", "warning", "critical", "unavailable"]


class HostMetricsResponse(BaseModel):
    cpu: HostCpuMetricsResponse
    memory: HostMemoryMetricsResponse
    disk: HostDiskMetricsResponse


class OpsDashboardSummaryResponse(BaseModel):
    systemd_total: int
    systemd_healthy: int
    pm2_total: int
    pm2_online: int
    pm2_unhealthy: int


class OpsDashboardResponse(BaseModel):
    generated_at: datetime
    overall_status: Literal["healthy", "warning", "critical"]
    host_metrics: HostMetricsResponse
    systemd_services: list[OpsServiceStatusResponse]
    pm2_processes: list[OpsProcessStatusResponse]
    summary: OpsDashboardSummaryResponse
    warnings: list[str]
