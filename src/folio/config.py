from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FOLIO_", env_file=".env", extra="ignore")

    database_url: str = Field(default="postgresql://folio:folio@postgres:5432/folio", repr=False)
    redis_url: str = Field(default="redis://redis:6379/0", repr=False)
    artifact_root: Path = Path("/data")
    models_path: str = "/models"
    development_mode: bool = False
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    max_pages: int = Field(default=100, gt=0)
    parser_timeout_seconds: int = Field(default=240, gt=0)
    job_timeout_seconds: int = Field(default=300, gt=0)
    worker_monitor_seconds: int = Field(default=10, gt=0)
    lease_seconds: int = Field(default=420, gt=0)
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_delays_seconds: tuple[int, ...] = (15, 60)
    retry_jitter_seconds: int = Field(default=5, ge=0)
    recovery_interval_seconds: int = Field(default=15, gt=0)
    dispatch_grace_seconds: int = Field(default=30, ge=1)
    batch_size: int = Field(default=20, ge=1, le=100)
    bootstrap_failure_limit: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def validate_execution_bounds(self):
        if self.job_timeout_seconds <= self.parser_timeout_seconds:
            raise ValueError("Job timeout must allow time after parsing to publish evidence")
        if self.lease_seconds <= self.job_timeout_seconds + 60 + self.worker_monitor_seconds:
            raise ValueError("Lease must outlast the RQ timeout and parent monitoring margin")
        if not self.retry_delays_seconds or min(self.retry_delays_seconds) < 0:
            raise ValueError("Retry delays must contain nonnegative seconds")
        return self

    def processing_config(self) -> dict:
        return {
            "parser": "docling",
            "parser_version": "2.148.0",
            "normalization_version": 2,
            "max_pages": self.max_pages,
            "timeout_seconds": self.parser_timeout_seconds,
            "models_path": self.models_path,
            "ocr_language": "eng",
            "lease_seconds": self.lease_seconds,
            "job_timeout_seconds": self.job_timeout_seconds,
            "worker_monitor_seconds": self.worker_monitor_seconds,
            "max_attempts": self.max_attempts,
            "retry_delays_seconds": self.retry_delays_seconds,
            "retry_jitter_seconds": self.retry_jitter_seconds,
        }
