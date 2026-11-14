"""Provider-neutral generation results and safe provider failures."""

from dataclasses import dataclass
from decimal import Decimal


class ProviderError(Exception):
    def __init__(self, code: str, retryable: bool = False, *, generation=None):
        self.code = code
        self.retryable = retryable
        self.generation = generation
        super().__init__(code)


@dataclass(frozen=True)
class Generation:
    content: str
    finish_reason: str
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: Decimal | None
    response_id: str | None
    model: str
    provider: str
    reasoning_tokens: int | None = None
    cost_basis: str = "provider_reported"
    cached_tokens: int | None = None
    pricing_version: str | None = None
    service_tier: str | None = None


def generation_usage(result) -> dict:
    """Persist observed usage and its pricing basis, including legacy results."""
    metadata = {
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "reasoning_tokens": getattr(result, "reasoning_tokens", None),
        "finish_reason": result.finish_reason,
        "model": result.model,
        "provider": result.provider,
        "response_id": result.response_id,
        "cost_basis": getattr(result, "cost_basis", "provider_reported"),
    }
    for name in ("cached_tokens", "pricing_version", "service_tier"):
        value = getattr(result, name, None)
        if value is not None:
            metadata[name] = value
    return metadata
