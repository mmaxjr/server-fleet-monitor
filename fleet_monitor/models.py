from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class ServerStatus(str, Enum):
    COLLECTING = "collecting"
    ONLINE = "online"
    OFFLINE = "offline"
    AUTHENTICATION_ERROR = "authentication_error"
    HOST_KEY_ERROR = "host_key_error"
    COLLECTION_ERROR = "collection_error"


class Settings(BaseModel):
    refresh_interval: int = Field(10, ge=2)
    ssh_timeout: int = Field(5, ge=1)
    max_concurrency: int = Field(10, ge=1, le=100)
    warning_threshold: float = Field(80, ge=0, le=100)
    critical_threshold: float = Field(90, ge=0, le=100)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "Settings":
        if self.warning_threshold >= self.critical_threshold:
            raise ValueError("warning_threshold deve ser menor que critical_threshold")
        return self


class ServerConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    host: str = Field(min_length=1)
    port: int = Field(22, ge=1, le=65535)
    username: str = Field(min_length=1)
    password: SecretStr


class Inventory(BaseModel):
    settings: Settings = Field(default_factory=Settings)
    servers: list[ServerConfig] = Field(min_length=1)


class DiskMetric(BaseModel):
    mountpoint: str
    percent: float | None = None
    total_bytes: int | None = None
    used_bytes: int | None = None


class InterfaceMetric(BaseModel):
    name: str
    bytes_sent: int | None = None
    bytes_recv: int | None = None


class ProcessMetric(BaseModel):
    pid: int
    name: str
    cpu_percent: float | None = None
    memory_percent: float | None = None


class Metrics(BaseModel):
    method: str
    cpu_percent: float | None = None
    memory_percent: float | None = None
    swap_percent: float | None = None
    load_average: tuple[float, float, float] | None = None
    uptime_seconds: float | None = None
    disks: list[DiskMetric] = Field(default_factory=list)
    interfaces: list[InterfaceMetric] = Field(default_factory=list)
    processes: list[ProcessMetric] = Field(default_factory=list)
    failed_services: list[str] = Field(default_factory=list)
    listening_ports: list[str] = Field(default_factory=list)


class ServerSnapshot(BaseModel):
    server_name: str
    status: ServerStatus
    collected_at: datetime | None = None
    metrics: Metrics | None = None
    error: str | None = None

