"""Explicit text-generation routes; no implicit retries or fallback."""

from copy import deepcopy
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

import httpx

from .deepseek import MODEL_ID as DEEPSEEK_MODEL_ID
from .tokens import BudgetError, check_budget, tokenizer_name


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


class OpenRouter:
    def __init__(self, policy: dict, api_key: str, *, transport=None):
        self.policy = deepcopy(policy)
        self._api_key = api_key
        self._transport = transport
        self._profile = None
        self._deepseek = policy.get("model_id") == DEEPSEEK_MODEL_ID
        self._provider = "fireworks" if self._deepseek else "openai"
        self._provider_name = "Fireworks" if self._deepseek else "OpenAI"
        if self._deepseek and policy.get("provider") == "together":
            self._provider, self._provider_name = "together", "Together"
        if (
            policy.get("provider") != self._provider
            or policy.get("base_url", "").rstrip("/") != "https://openrouter.ai/api/v1"
            or policy.get("reasoning_effort")
            not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
        ):
            raise ProviderError("SUMMARY_MODEL_UNAVAILABLE")
        try:
            self._tokenizer = tokenizer_name(policy.get("model_id"))
        except BudgetError:
            raise ProviderError("SUMMARY_MODEL_UNAVAILABLE") from None

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            with httpx.Client(
                base_url=self.policy["base_url"].rstrip("/") + "/",
                timeout=self.policy["timeout_seconds"],
                transport=self._transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.request(method, path, **kwargs)
        except httpx.TimeoutException:
            raise ProviderError("SUMMARY_PROVIDER_TIMEOUT", retryable=True) from None
        except httpx.TransportError:
            raise ProviderError("SUMMARY_PROVIDER_UNAVAILABLE", retryable=True) from None
        try:
            body = response.json()
        except ValueError:
            body = None
        billing = _billing(body) if method == "POST" and isinstance(body, dict) else None
        if response.status_code == 429:
            raise ProviderError("SUMMARY_PROVIDER_RATE_LIMIT", retryable=True, generation=billing)
        if response.status_code >= 500:
            raise ProviderError("SUMMARY_PROVIDER_UNAVAILABLE", retryable=True, generation=billing)
        if not 200 <= response.status_code < 300:
            raise ProviderError("SUMMARY_PROVIDER_REJECTED", generation=billing)
        if not isinstance(body, dict) or "error" in body:
            raise ProviderError("SUMMARY_PROVIDER_RESPONSE_INVALID", generation=billing)
        return body

    def profile(self) -> dict:
        if self._profile is not None:
            return deepcopy(self._profile)
        body = self._request("GET", f"models/{self.policy['model_id']}/endpoints")
        try:
            data = body["data"]
            if data["id"] != self.policy["model_id"]:
                raise ValueError
            endpoints = data["endpoints"]
            tags = [endpoint["tag"] for endpoint in endpoints]
            if any(not isinstance(tag, str) or not tag for tag in tags):
                raise ValueError
            routes = [endpoint for endpoint in endpoints if endpoint["tag"] == self._provider]
            if len(routes) != 1:
                raise ValueError
            route = routes[0]
            if (
                route.get("service_tier") is not None
                or route.get("status") != 0
                or route.get("provider_name") != self._provider_name
            ):
                raise ValueError
            context, prompt, output = (
                route["context_length"],
                route["max_prompt_tokens"],
                route["max_completion_tokens"],
            )
            limits = (
                (context, output)
                if self._deepseek and prompt is None
                else (context, prompt, output)
            )
            if any(type(value) is not int or value <= 0 for value in limits):
                raise ValueError
            if (prompt is not None and prompt > context) or output > context:
                raise ValueError
            catalog = self._request("GET", "models")
            models = [model for model in catalog["data"] if model["id"] == data["id"]]
            if len(models) != 1:
                raise ValueError
            reasoning = models[0].get("reasoning") or {}
            supported_efforts = reasoning.get("supported_efforts", [])
            effort = self.policy["reasoning_effort"]
            if not isinstance(supported_efforts, list) or any(
                not isinstance(value, str) for value in supported_efforts
            ):
                raise ValueError
            if not reasoning and effort == "none":
                effort = None
            elif effort not in supported_efforts or (
                effort == "none" and reasoning.get("mandatory") is True
            ):
                raise ValueError
            required = {"max_tokens", "response_format", "structured_outputs"}
            if effort is not None:
                required.add("reasoning")
            if not required.issubset(route["supported_parameters"]):
                raise ValueError
            pricing = route["pricing"]
            input_price, output_price = Decimal(pricing["prompt"]), Decimal(pricing["completion"])
            if any(not price.is_finite() or price < 0 for price in (input_price, output_price)):
                raise ValueError
            # This text-only request uses no tools, images, cache writes or optional plugins.
            # Reject fixed fees and unknown price tiers instead of under-reserving their cost.
            if pricing.get("overrides") or any(
                Decimal(str(pricing.get(key, "0"))) != 0
                for key in ("request", "input_cache_write", "internal_reasoning")
            ):
                raise ValueError
            profile = {
                "model_id": data["id"],
                "provider": self._provider,
                "tokenizer": self._tokenizer,
                "context_tokens": context,
                "max_prompt_tokens": prompt,
                "max_completion_tokens": output,
                "input_price_per_million": str(input_price * 1_000_000),
                "output_price_per_million": str(output_price * 1_000_000),
                "service_tier": None if self._deepseek else "default",
                "reasoning_effort": effort,
            }
            if self._deepseek:
                # Root provider tags also match subroutes. Explicitly exclude every
                # observed variant so regional/spot pricing cannot replace this route.
                profile["excluded_providers"] = sorted(
                    {tag for tag in tags if tag.startswith(self._provider + "/")}
                )
        except (AttributeError, KeyError, TypeError, ValueError, InvalidOperation):
            raise ProviderError("SUMMARY_MODEL_UNAVAILABLE") from None
        self._profile = profile
        return deepcopy(profile)

    def generate(
        self, messages: list[dict], schema: dict, *, schema_name="folio_summary"
    ) -> Generation:
        profile = self.profile()
        check_budget(messages, schema, self.policy, profile)
        if not self._api_key:
            raise ProviderError("SUMMARY_PROVIDER_NOT_CONFIGURED")
        payload = {
            "model": self.policy["model_id"],
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
            "max_tokens": self.policy["max_output_tokens"],
            "stream": False,
            "transforms": [],
            "plugins": [],
            "provider": {
                "only": [self._provider],
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": "deny",
                "max_price": {
                    "prompt": profile["input_price_per_million"],
                    "completion": profile["output_price_per_million"],
                },
            },
        }
        if self._deepseek:
            payload["provider"]["ignore"] = profile["excluded_providers"]
        else:
            payload["service_tier"] = "default"
        if profile["reasoning_effort"] is not None:
            payload["reasoning"] = {"effort": profile["reasoning_effort"]}
        body = self._request(
            "POST",
            "chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        billing = _billing(body)
        try:
            choice = body["choices"][0]
            message = choice["message"]
            content = message.get("content")
            finish_reason = choice["finish_reason"]
            if message.get("refusal"):
                content, finish_reason = "", "refusal"
            elif content is None and finish_reason != "stop":
                content = ""
            if not isinstance(content, str) or not isinstance(finish_reason, str):
                raise ValueError
            if finish_reason not in {
                "stop",
                "length",
                "content_filter",
                "tool_calls",
                "function_call",
                "error",
                "refusal",
            }:
                finish_reason = "unknown"
            if body["model"] != self.policy["model_id"] or body["provider"] != self._provider_name:
                raise ValueError
            usage = body.get("usage") or {}
            if usage.get("cost") is not None and billing.cost_usd is None:
                raise ValueError
            return replace(
                billing,
                content=content,
                finish_reason=finish_reason,
                provider=self._provider,
            )
        except (AttributeError, KeyError, IndexError, TypeError, ValueError, InvalidOperation):
            raise ProviderError("SUMMARY_PROVIDER_RESPONSE_INVALID", generation=billing) from None


def _billing(body: dict) -> Generation:
    """Retain safe usage independently of whether the answer is usable."""
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    details = usage.get("completion_tokens_details")
    cost = None
    try:
        if usage.get("cost") is not None:
            cost = Decimal(str(usage["cost"]))
            if not cost.is_finite() or cost < 0:
                cost = None
    except InvalidOperation:
        pass
    return Generation(
        content="",
        finish_reason="unknown",
        prompt_tokens=_usage_count(usage.get("prompt_tokens")),
        completion_tokens=_usage_count(usage.get("completion_tokens")),
        cost_usd=cost,
        response_id=body.get("id") if isinstance(body.get("id"), str) else None,
        model=body.get("model") if isinstance(body.get("model"), str) else "",
        provider=body.get("provider", "").lower() if isinstance(body.get("provider"), str) else "",
        reasoning_tokens=_usage_count(details.get("reasoning_tokens"))
        if isinstance(details, dict)
        else None,
    )


def _usage_count(value) -> int | None:
    return value if type(value) is int and value >= 0 else None
