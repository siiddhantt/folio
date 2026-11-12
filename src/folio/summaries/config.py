from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError

from folio.ai.budget import BudgetSettings
from folio.summaries.preparation import PREPARATION_VERSION, PROMPT_VERSION, SCHEMA_VERSION


class SummaryCredentials(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)
    api_key: SecretStr = Field(default=SecretStr(""), validation_alias="OPENROUTER_API_KEY")


class SummarySettings(SummaryCredentials, BudgetSettings):
    model_config = SettingsConfigDict(
        env_prefix="FOLIO_SUMMARY_", env_file=".env", extra="ignore", populate_by_name=True
    )

    enabled: bool = False
    model_id: str = "deepseek/deepseek-v4.1-flash-1017"
    provider: str = "together"
    input_limit_tokens: int = Field(default=64000, gt=0)
    max_output_tokens: int = Field(default=16384, gt=0)
    token_margin: int = Field(default=2048, gt=0)
    reasoning_effort: str = "none"
    timeout_seconds: int = Field(default=90, gt=0)
    max_attempts: int = Field(default=2, ge=1, le=2)
    base_url: str = Field(
        default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL"
    )

    def policy(self, runtime):
        policy = self.model_dump(mode="json", exclude={"api_key"})
        policy.update(
            reservation_version=2,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            preparation_version=PREPARATION_VERSION,
            job_timeout_seconds=runtime.job_timeout_seconds,
            lease_seconds=runtime.lease_seconds,
            retry_delays_seconds=list(runtime.retry_delays_seconds),
            retry_jitter_seconds=runtime.retry_jitter_seconds,
        )
        return policy


def capture_policy(runtime):
    """Summary configuration cannot prevent otherwise usable evidence publication."""
    try:
        return SummarySettings().policy(runtime)
    except (ValueError, SettingsError):
        return {"enabled": False, "unavailable_code": "SUMMARY_CONFIGURATION_INVALID"}
