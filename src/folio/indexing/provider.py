"""One explicit embedding route with no implicit retries or fallback."""

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import httpx

MODEL = "openai/text-embedding-3-small"
DIMENSIONS = 1536


class EmbeddingError(Exception):
    def __init__(self, code, *, retryable=False, metadata=None, cost_usd=None):
        super().__init__(code)
        self.code, self.retryable = code, retryable
        self.metadata, self.cost_usd = metadata or {}, cost_usd


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    metadata: dict
    cost_usd: Decimal | None


class OpenRouterEmbeddings:
    gateway = "openrouter"
    base_url = "https://openrouter.ai/api/v1/"

    def __init__(self, policy, api_key, *, transport=None):
        self.policy, self._api_key, self._transport = dict(policy), api_key, transport
        if (
            policy.get("gateway", "openrouter") != self.gateway
            or policy["model_id"] != MODEL
            or policy["provider"] != "openai"
            or policy["dimensions"] != DIMENSIONS
        ):
            raise EmbeddingError("EMBEDDING_MODEL_UNAVAILABLE")

    def _request(self, method, path, **kwargs):
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.policy["timeout_seconds"],
                transport=self._transport,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = client.request(method, path, **kwargs)
        except httpx.TimeoutException:
            raise EmbeddingError("EMBEDDING_TIMEOUT", retryable=True) from None
        except httpx.TransportError:
            raise EmbeddingError("EMBEDDING_PROVIDER_UNAVAILABLE", retryable=True) from None
        if response.status_code == 429 or response.status_code >= 500:
            raise EmbeddingError("EMBEDDING_PROVIDER_UNAVAILABLE", retryable=True)
        if not response.is_success:
            raise EmbeddingError("EMBEDDING_PROVIDER_REJECTED")
        try:
            body = response.json()
            if not isinstance(body, dict) or "error" in body:
                raise ValueError
            return body
        except ValueError:
            raise EmbeddingError("EMBEDDING_RESPONSE_INVALID") from None

    def profile(self):
        body = self._request("GET", f"models/{MODEL}/endpoints")
        try:
            data = body["data"]
            (route,) = [r for r in data["endpoints"] if r["tag"] == "openai"]
            price = Decimal(route["pricing"]["prompt"])
            if (
                data["id"] != MODEL
                or route["status"] != 0
                or not price.is_finite()
                or price < 0
                or price * 1_000_000 > Decimal(self.policy["input_price_per_million"])
                or route["context_length"] < 8192
                or route["pricing"].get("overrides")
                or Decimal(str(route["pricing"].get("request", 0))) != 0
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise EmbeddingError("EMBEDDING_MODEL_UNAVAILABLE") from None
        return {
            "model_id": MODEL,
            "provider": "openai",
            "dimensions": DIMENSIONS,
            "max_input_tokens": 8192,
            "input_price_per_million": str(price * 1_000_000),
        }

    def _payload(self, texts):
        return {
            "model": MODEL,
            "input": texts,
            "encoding_format": "float",
            "provider": {
                "only": ["openai"],
                "allow_fallbacks": False,
                "data_collection": "deny",
                "max_price": {"prompt": self.policy["input_price_per_million"]},
            },
        }

    def embed(self, texts):
        if not self._api_key:
            raise EmbeddingError("EMBEDDING_PROVIDER_NOT_CONFIGURED")
        body = self._request(
            "POST",
            "embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=self._payload(texts),
        )
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        cost = None
        try:
            if usage.get("cost") is not None:
                cost = Decimal(str(usage["cost"]))
                if not cost.is_finite() or cost < 0:
                    cost = None
        except InvalidOperation:
            pass
        metadata = {
            "model": body.get("model"),
            "response_id": body.get("id"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "requested_provider": "openai",
        }
        if self.gateway == "openai":
            prompt, total = usage.get("prompt_tokens"), usage.get("total_tokens")
            valid_usage = (
                body.get("model") == "text-embedding-3-small"
                and type(prompt) is int
                and prompt >= 0
                and type(total) is int
                and total == prompt
            )
            cost = Decimal(prompt) * Decimal("0.02") / 1_000_000 if valid_usage else None
            metadata.update(
                {
                    "gateway": "openai",
                    "cost_basis": "token_estimate" if cost is not None else "unknown",
                    "pricing_version": "openai-text-embedding-3-small-2026-11-15",
                }
            )
        try:
            if body["model"] not in {MODEL, "text-embedding-3-small"}:
                raise ValueError
            entries = body["data"]
            if len(entries) != len(texts):
                raise ValueError
            vectors = [None] * len(texts)
            for entry in entries:
                index, vector = entry["index"], entry["embedding"]
                if (
                    type(index) is not int
                    or not 0 <= index < len(texts)
                    or vectors[index] is not None
                    or not isinstance(vector, list)
                    or len(vector) != DIMENSIONS
                    or any(
                        type(v) not in {int, float}
                        or not math.isfinite(v)
                        or abs(v) > 3.4028234663852886e38
                        for v in vector
                    )
                    or not any(v != 0 for v in vector)
                ):
                    raise ValueError
                vectors[index] = vector
            if any(v is None for v in vectors):
                raise ValueError
        except (KeyError, TypeError, ValueError, OverflowError):
            raise EmbeddingError(
                "EMBEDDING_RESPONSE_INVALID", metadata=metadata, cost_usd=cost
            ) from None
        return EmbeddingResult(vectors, metadata, cost)


class OpenAIEmbeddings(OpenRouterEmbeddings):
    gateway = "openai"
    base_url = "https://api.openai.com/v1/"

    def profile(self):
        # Reviewed against OpenAI model and embeddings reference, November 15, 2026.
        if Decimal(self.policy["input_price_per_million"]) < Decimal("0.02"):
            raise EmbeddingError("EMBEDDING_MODEL_UNAVAILABLE")
        return {
            "model_id": MODEL,
            "provider": "openai",
            "gateway": "openai",
            "dimensions": DIMENSIONS,
            "max_input_tokens": 8192,
            "input_price_per_million": "0.02",
            "pricing_version": "openai-text-embedding-3-small-2026-11-15",
        }

    def _payload(self, texts):
        return {
            "model": "text-embedding-3-small",
            "input": texts,
            "encoding_format": "float",
            "dimensions": DIMENSIONS,
        }


def embedding_client(policy, *, transport=None):
    from folio.ai.routing import GenerationCredentials

    gateway = policy.get("gateway", "openrouter")
    if gateway not in ("openrouter", "openai"):
        raise EmbeddingError("EMBEDDING_MODEL_UNAVAILABLE")
    key = getattr(GenerationCredentials(), gateway).get_secret_value()
    if not key:
        raise EmbeddingError("EMBEDDING_PROVIDER_NOT_CONFIGURED")
    adapter = OpenAIEmbeddings if gateway == "openai" else OpenRouterEmbeddings
    return adapter(policy, key, transport=transport)
