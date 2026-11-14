"""Direct generation with a reviewed, versioned GPT-5.2 profile."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

import httpx

from .generation import Generation, ProviderError
from .tokens import check_budget, tokenizer_name

PROFILE_VERSION = "openai-gpt-5.2-2026-11-13"
MODEL_ID = "openai/gpt-5.2"
NATIVE_MODEL_ID = "gpt-5.2-2025-12-11"


class OpenAI:
    def __init__(self, policy: dict, api_key: str, *, transport=None):
        base_url = policy.get("base_url")
        effort = policy.get("reasoning_effort")
        if (
            policy.get("model_id") != MODEL_ID
            or policy.get("provider") != "openai"
            or policy.get("gateway") != "openai"
            or not isinstance(base_url, str)
            or base_url.rstrip("/") != "https://api.openai.com/v1"
            or policy.get("provider_profile_version") != PROFILE_VERSION
            or effort not in ("none", "low", "medium", "high", "xhigh")
        ):
            raise ProviderError("SUMMARY_MODEL_UNAVAILABLE")
        self.policy = deepcopy(policy)
        self._api_key = api_key
        self._transport = transport

    def profile(self) -> dict:
        # Reviewed November 13, 2026: developers.openai.com/api/docs/models/gpt-5.2.
        # The combined context check also reserves room for the selected output bound.
        return {
            "model_id": MODEL_ID,
            "native_model_id": NATIVE_MODEL_ID,
            "provider": "openai",
            "gateway": "openai",
            "provider_profile_version": PROFILE_VERSION,
            "tokenizer": tokenizer_name(MODEL_ID),
            "context_tokens": 400000,
            "max_prompt_tokens": 400000,
            "max_completion_tokens": 128000,
            "input_price_per_million": "1.75",
            "cached_input_price_per_million": "0.175",
            "output_price_per_million": "14",
            "service_tier": "default",
            "reasoning_effort": self.policy["reasoning_effort"],
        }

    def generate(
        self, messages: list[dict], schema: dict, *, schema_name="folio_summary"
    ) -> Generation:
        profile = self.profile()
        check_budget(messages, schema, self.policy, profile)
        if not self._api_key:
            raise ProviderError("SUMMARY_PROVIDER_NOT_CONFIGURED")
        payload = {
            "model": NATIVE_MODEL_ID,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
            "max_completion_tokens": self.policy["max_output_tokens"],
            "reasoning_effort": profile["reasoning_effort"],
            "service_tier": "default",
            "stream": False,
        }
        try:
            with httpx.Client(
                base_url="https://api.openai.com/v1/",
                timeout=self.policy["timeout_seconds"],
                transport=self._transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.post(
                    "chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
        except httpx.TimeoutException:
            raise ProviderError("SUMMARY_PROVIDER_TIMEOUT", retryable=True) from None
        except httpx.TransportError:
            raise ProviderError("SUMMARY_PROVIDER_UNAVAILABLE", retryable=True) from None
        try:
            body = response.json()
        except ValueError:
            body = None
        billing = _billing(body) if isinstance(body, dict) else None
        if response.status_code == 429:
            raise ProviderError("SUMMARY_PROVIDER_RATE_LIMIT", retryable=True, generation=billing)
        if response.status_code >= 500:
            raise ProviderError("SUMMARY_PROVIDER_UNAVAILABLE", retryable=True, generation=billing)
        if not 200 <= response.status_code < 300:
            raise ProviderError("SUMMARY_PROVIDER_REJECTED", generation=billing)
        if not isinstance(body, dict) or "error" in body:
            raise ProviderError("SUMMARY_PROVIDER_RESPONSE_INVALID", generation=billing)
        try:
            if body["model"] != NATIVE_MODEL_ID or body["service_tier"] != "default":
                raise ValueError
            choice = body["choices"][0]
            message = choice["message"]
            content = message.get("content")
            finish = choice["finish_reason"]
            if message.get("refusal"):
                content, finish = "", "refusal"
            elif content is None and finish != "stop":
                content = ""
            if not isinstance(content, str) or not isinstance(finish, str):
                raise ValueError
            if finish not in (
                "stop",
                "length",
                "content_filter",
                "tool_calls",
                "function_call",
                "refusal",
            ):
                finish = "unknown"
            return replace(billing, content=content, finish_reason=finish)
        except (AttributeError, KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("SUMMARY_PROVIDER_RESPONSE_INVALID", generation=billing) from None


def _billing(body: dict) -> Generation:
    """Preserve valid observations without inventing usage missing from a response."""
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    prompt_details = usage.get("prompt_tokens_details")
    completion_details = usage.get("completion_tokens_details")
    prompt = _usage_count(usage.get("prompt_tokens"))
    output = _usage_count(usage.get("completion_tokens"))
    cached = (
        _usage_count(prompt_details.get("cached_tokens"))
        if isinstance(prompt_details, dict)
        else None
    )
    reasoning = (
        _usage_count(completion_details.get("reasoning_tokens"))
        if isinstance(completion_details, dict)
        else None
    )
    valid = (
        body.get("model") == NATIVE_MODEL_ID
        and body.get("service_tier") == "default"
        and prompt is not None
        and output is not None
        and cached is not None
    )
    if valid:
        valid = cached <= prompt and (reasoning is None or reasoning <= output)
        if "total_tokens" in usage:
            valid = valid and _usage_count(usage["total_tokens"]) == prompt + output
    if isinstance(completion_details, dict) and "reasoning_tokens" in completion_details:
        valid = valid and reasoning is not None
    elif completion_details is not None:
        valid = valid and isinstance(completion_details, dict)
    cost = None
    if valid:
        cost = (
            (prompt - cached) * Decimal("1.75") + cached * Decimal("0.175") + output * Decimal("14")
        ) / Decimal(1_000_000)
    return Generation(
        content="",
        finish_reason="unknown",
        prompt_tokens=prompt,
        completion_tokens=output,
        cost_usd=cost,
        response_id=body.get("id") if isinstance(body.get("id"), str) else None,
        model=body.get("model") if isinstance(body.get("model"), str) else "",
        provider="openai",
        reasoning_tokens=reasoning,
        cost_basis="token_estimate" if cost is not None else "unknown",
        cached_tokens=cached,
        pricing_version=PROFILE_VERSION if cost is not None else None,
        service_tier=body.get("service_tier")
        if isinstance(body.get("service_tier"), str)
        else None,
    )


def _usage_count(value) -> int | None:
    return value if type(value) is int and value >= 0 else None
