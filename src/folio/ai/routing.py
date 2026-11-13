"""Select a generation service from saved policy, never from a worker's current default."""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .openai import PROFILE_VERSION

Gateway = Literal["openrouter", "openai"]


def gateway_policy(gateway: Gateway) -> dict:
    if gateway == "openai":
        return {
            "gateway": gateway,
            "base_url": "https://api.openai.com/v1",
            "provider_profile_version": PROFILE_VERSION,
        }
    return {"gateway": gateway, "base_url": "https://openrouter.ai/api/v1"}


class GenerationCredentials(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    openrouter: SecretStr = Field(default=SecretStr(""), validation_alias="OPENROUTER_API_KEY")
    openai: SecretStr = Field(default=SecretStr(""), validation_alias="OPENAI_API_KEY")


def generation_client(policy: dict, *, transport=None):
    from .generation import ProviderError
    from .openai import OpenAI
    from .openrouter import OpenRouter

    gateway = policy.get("gateway", "openrouter")
    if gateway not in ("openrouter", "openai"):
        raise ProviderError("SUMMARY_MODEL_UNAVAILABLE")
    key = getattr(GenerationCredentials(), gateway).get_secret_value()
    if not key:
        raise ProviderError("SUMMARY_PROVIDER_NOT_CONFIGURED")
    adapter = OpenAI if gateway == "openai" else OpenRouter
    return adapter(policy, key, transport=transport)
