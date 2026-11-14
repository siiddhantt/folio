from decimal import Decimal
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from folio.ai.budget import BudgetSettings


class IndexSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FOLIO_INDEX_", env_file=".env", extra="ignore")

    enabled: bool = False
    model_id: Literal["openai/text-embedding-3-small"] = "openai/text-embedding-3-small"
    provider: Literal["openai"] = "openai"
    dimensions: Literal[1536] = 1536
    chunk_tokens: int = Field(default=512, ge=32, le=8192)
    batch_size: int = Field(default=32, ge=1, le=32)
    max_chunks: int = Field(default=4096, ge=1, le=10000)
    timeout_seconds: int = Field(default=60, ge=1)
    max_attempts: int = Field(default=2, ge=1, le=3)
    input_price_per_million: Decimal = Field(default=Decimal("0.02"), gt=0, le=Decimal("0.02"))

    def policy(self, runtime):
        budget = BudgetSettings()
        return self.model_dump(mode="json") | {
            "budget_usd": str(budget.budget_usd),
            "document_budget_usd": str(budget.document_budget_usd),
            "job_timeout_seconds": runtime.job_timeout_seconds,
            "lease_seconds": runtime.lease_seconds,
            "retry_delays_seconds": list(runtime.retry_delays_seconds),
            "retry_jitter_seconds": runtime.retry_jitter_seconds,
        }


def capture_policy(runtime):
    try:
        return IndexSettings().policy(runtime)
    except ValueError:
        return {"enabled": False, "unavailable_code": "INDEX_CONFIGURATION_INVALID"}
