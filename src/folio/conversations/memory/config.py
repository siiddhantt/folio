from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FOLIO_MEMORY_", env_file=".env", extra="ignore")
    trigger_tokens: int = Field(default=6000, gt=0)
    target_tokens: int = Field(default=3000, gt=0)
    keep_turns: int = Field(default=2, ge=2)
    wait_seconds: int = Field(default=600, gt=0)
    model_id: str = "openai/gpt-5.2"
    provider: str = "openai"
    input_limit_tokens: int = Field(default=16384, gt=0)
    max_output_tokens: int = Field(default=2048, gt=0)
    timeout_seconds: int = Field(default=90, gt=0)
    reasoning_effort: str = "none"

    @model_validator(mode="after")
    def ordered_thresholds(self):
        if self.target_tokens >= self.trigger_tokens:
            raise ValueError("Memory target must be below its trigger")
        return self

    def policy(self, hard_limit):
        if self.trigger_tokens > hard_limit:
            raise ValueError("Memory trigger must not exceed the history limit")
        return self.model_dump(mode="json") | {"version": 1}
