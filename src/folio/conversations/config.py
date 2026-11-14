from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from folio.ai.budget import BudgetSettings
from folio.ai.routing import Gateway, gateway_policy


class ChatSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FOLIO_CHAT_", env_file=".env", extra="ignore")
    model_id: str = "openai/gpt-5.2"
    provider: str = "openai"
    gateway: Gateway = "openrouter"
    input_limit_tokens: int = Field(default=16384, gt=0)
    max_output_tokens: int = Field(default=4096, gt=0)
    token_margin: int = Field(default=2048, gt=0)
    reasoning_effort: str = "none"
    timeout_seconds: int = Field(default=90, gt=0)
    retrieval_chunks: int = Field(default=6, ge=1, le=12)
    history_limit_tokens: int = Field(default=8000, gt=0)
    rewrite_model_id: str = "openai/gpt-5.2"
    rewrite_provider: str = "openai"
    rewrite_gateway: Gateway = "openrouter"
    rewrite_input_limit_tokens: int = Field(default=16384, gt=0)
    rewrite_max_output_tokens: int = Field(default=1024, gt=0)
    rewrite_reasoning_effort: str = "none"
    rewrite_timeout_seconds: int = Field(default=90, gt=0)

    def policy(self, runtime):
        from .memory.config import MemorySettings

        return (
            self.model_dump(mode="json")
            | BudgetSettings().model_dump(mode="json")
            | {
                "reservation_version": 2,
                "prompt_version": 3,
                "schema_version": 3,
                "rewrite_prompt_version": 2,
                "retrieval_version": 2,
                "memory": MemorySettings().policy(self.history_limit_tokens),
                "job_timeout_seconds": runtime.job_timeout_seconds,
                "lease_seconds": runtime.lease_seconds,
                "max_attempts": 2,
                "retry_delays_seconds": list(runtime.retry_delays_seconds),
            }
            | gateway_policy(self.gateway)
            | {
                f"rewrite_{key}": value
                for key, value in gateway_policy(self.rewrite_gateway).items()
            }
        )


def rewrite_policy(policy):
    stage = policy | {
        key: policy[f"rewrite_{key}"]
        for key in (
            "model_id",
            "provider",
            "input_limit_tokens",
            "max_output_tokens",
            "reasoning_effort",
            "timeout_seconds",
        )
    }
    stage.pop("provider_profile_version", None)
    if "rewrite_provider_profile_version" in policy:
        stage["provider_profile_version"] = policy["rewrite_provider_profile_version"]
    return stage | {
        "gateway": policy.get("rewrite_gateway", "openrouter"),
        "base_url": policy.get("rewrite_base_url", "https://openrouter.ai/api/v1"),
    }
