from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from folio.ai.budget import BudgetSettings


class ChatSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FOLIO_CHAT_", env_file=".env", extra="ignore")
    model_id: str = "openai/gpt-5.2"
    provider: str = "openai"
    input_limit_tokens: int = Field(default=16384, gt=0)
    max_output_tokens: int = Field(default=4096, gt=0)
    token_margin: int = Field(default=2048, gt=0)
    reasoning_effort: str = "none"
    timeout_seconds: int = Field(default=90, gt=0)
    retrieval_chunks: int = Field(default=6, ge=1, le=12)

    def policy(self, runtime):
        return (
            self.model_dump(mode="json")
            | BudgetSettings().model_dump(mode="json")
            | {
                "base_url": "https://openrouter.ai/api/v1",
                "reservation_version": 2,
                "prompt_version": 2,
                "schema_version": 2,
                "retrieval_version": 1,
                "job_timeout_seconds": runtime.job_timeout_seconds,
                "lease_seconds": runtime.lease_seconds,
                "max_attempts": 2,
                "retry_delays_seconds": list(runtime.retry_delays_seconds),
            }
        )
