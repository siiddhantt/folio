import json
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from folio.ai import BudgetError, ProviderError
from folio.ai.generation import generation_usage
from folio.ai.openai import OpenAI

POLICY = {
    "model_id": "openai/gpt-5.2",
    "provider": "openai",
    "gateway": "openai",
    "base_url": "https://api.openai.com/v1",
    "provider_profile_version": "openai-gpt-5.2-2026-11-13",
    "input_limit_tokens": 16384,
    "max_output_tokens": 4096,
    "token_margin": 2048,
    "reasoning_effort": "none",
    "timeout_seconds": 90,
    "reservation_version": 2,
}
MESSAGES = [{"role": "user", "content": "Evidence S1: The trial lasted six weeks."}]
SCHEMA = {
    "type": "object",
    "properties": {"overview": {"type": "string"}},
    "required": ["overview"],
    "additionalProperties": False,
}


def completion():
    return {
        "id": "chatcmpl-synthetic",
        "model": "gpt-5.2-2025-12-11",
        "service_tier": "default",
        "choices": [{"finish_reason": "stop", "message": {"content": '{"overview":"Six weeks"}'}}],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "total_tokens": 1100,
            "prompt_tokens_details": {"cached_tokens": 200},
            "completion_tokens_details": {"reasoning_tokens": 20},
        },
    }


def test_profile_pins_standard_gpt52_without_a_network_request():
    def respond(request):
        raise AssertionError("The reviewed profile requires no network request")

    client = OpenAI(POLICY, "synthetic-key", transport=httpx.MockTransport(respond))
    profile = client.profile()
    assert profile["model_id"] == "openai/gpt-5.2"
    assert profile["native_model_id"] == "gpt-5.2-2025-12-11"
    assert profile["provider_profile_version"] == "openai-gpt-5.2-2026-11-13"
    assert profile["tokenizer"] == "o200k_base"
    assert profile["provider"] == "openai"
    assert profile["context_tokens"] == 400000
    assert profile["max_prompt_tokens"] == 400000
    assert profile["max_completion_tokens"] == 128000
    assert profile["service_tier"] == "default"
    assert profile["reasoning_effort"] == "none"
    assert Decimal(profile["input_price_per_million"]) == Decimal("1.75")
    assert Decimal(profile["cached_input_price_per_million"]) == Decimal("0.175")
    assert Decimal(profile["output_price_per_million"]) == Decimal("14")
    profile["input_price_per_million"] = "0"
    assert client.profile()["input_price_per_million"] == "1.75"


@pytest.mark.parametrize(
    "changes",
    [
        {"model_id": "openai/gpt-5-mini"},
        {"model_id": "gpt-5.2"},
        {"provider": "together"},
        {"gateway": "openrouter"},
        {"base_url": "https://example.invalid/v1"},
        {"provider_profile_version": "old-version"},
        {"provider_profile_version": None},
        {"reasoning_effort": "minimal"},
        {"reasoning_effort": "max"},
    ],
)
def test_unreviewed_model_route_or_profile_is_rejected_before_network(changes):
    def respond(request):
        raise AssertionError("Invalid policy must fail before any request")

    with pytest.raises(ProviderError, match="^SUMMARY_MODEL_UNAVAILABLE$"):
        OpenAI({**POLICY, **changes}, "synthetic-key", transport=httpx.MockTransport(respond))


def test_usage_metadata_keeps_legacy_results_and_optional_price_provenance():
    result = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=20,
        finish_reason="stop",
        model="openai/gpt-5.2",
        provider="openai",
        response_id="synthetic-response",
    )
    assert generation_usage(result) == {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "reasoning_tokens": None,
        "finish_reason": "stop",
        "model": "openai/gpt-5.2",
        "provider": "openai",
        "response_id": "synthetic-response",
        "cost_basis": "provider_reported",
    }
    result.cost_basis = "token_estimate"
    result.cached_tokens = 50
    result.pricing_version = "openai-gpt-5.2-2026-11-13"
    result.service_tier = "default"
    metadata = generation_usage(result)
    assert metadata["cost_basis"] == "token_estimate"
    assert metadata["cached_tokens"] == 50
    assert metadata["pricing_version"] == "openai-gpt-5.2-2026-11-13"
    assert metadata["service_tier"] == "default"


def test_direct_request_returns_an_explicit_cached_token_estimate():
    requests = []

    def respond(request):
        requests.append(request)
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        assert request.method == "POST"
        assert request.headers["authorization"] == "Bearer synthetic-key"
        assert json.loads(request.content) == {
            "model": "gpt-5.2-2025-12-11",
            "messages": MESSAGES,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "folio_answer", "strict": True, "schema": SCHEMA},
            },
            "max_completion_tokens": 4096,
            "reasoning_effort": "none",
            "service_tier": "default",
            "stream": False,
        }
        return httpx.Response(200, json=completion())

    client = OpenAI(POLICY, "synthetic-key", transport=httpx.MockTransport(respond))
    result = client.generate(MESSAGES, SCHEMA, schema_name="folio_answer")
    assert len(requests) == 1
    assert result.content == '{"overview":"Six weeks"}'
    assert result.finish_reason == "stop"
    assert (result.prompt_tokens, result.completion_tokens, result.reasoning_tokens) == (
        1000,
        100,
        20,
    )
    assert result.cached_tokens == 200
    assert result.cost_usd == Decimal("0.002835")
    assert result.cost_basis == "token_estimate"
    assert result.pricing_version == "openai-gpt-5.2-2026-11-13"
    assert result.service_tier == "default"
    assert result.model == "gpt-5.2-2025-12-11"
    assert result.provider == "openai"
    assert result.response_id == "chatcmpl-synthetic"


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        "unusable usage",
        {"prompt_tokens": 1000, "completion_tokens": 100},
        {
            "prompt_tokens": True,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
        {
            "prompt_tokens": 1000,
            "completion_tokens": -1,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
        {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 1001},
        },
        {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": -1},
        },
        {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": "0"},
        },
        {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 101},
        },
        {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 0},
            "total_tokens": 100,
        },
    ],
)
def test_missing_or_inconsistent_usage_never_becomes_a_known_charge(usage):
    body = {**completion(), "usage": usage}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    result = OpenAI(POLICY, "synthetic-key", transport=transport).generate(MESSAGES, SCHEMA)
    assert result.content == '{"overview":"Six weeks"}'
    assert result.cost_usd is None
    assert result.cost_basis == "unknown"


@pytest.mark.parametrize(
    "message,finish,expected",
    [
        ({"content": None, "refusal": "private refusal explanation"}, "stop", "refusal"),
        ({"content": None}, "length", "length"),
        ({"content": None}, "content_filter", "content_filter"),
        ({"content": "partial"}, "private provider diagnostic", "unknown"),
    ],
)
def test_unsuccessful_answers_retain_their_usage_estimate(message, finish, expected):
    body = {**completion(), "choices": [{"message": message, "finish_reason": finish}]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    result = OpenAI(POLICY, "synthetic-key", transport=transport).generate(MESSAGES, SCHEMA)
    assert result.finish_reason == expected
    assert isinstance(result.content, str)
    assert "private" not in result.content
    assert result.cost_usd == Decimal("0.002835")
    assert result.cost_basis == "token_estimate"


@pytest.mark.parametrize(
    "changes,expected_cost",
    [
        ({"choices": []}, Decimal("0.002835")),
        ({"choices": [{"message": None}]}, Decimal("0.002835")),
        (
            {"choices": [{"message": {"content": ["private content"]}, "finish_reason": "stop"}]},
            Decimal("0.002835"),
        ),
        (
            {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]},
            Decimal("0.002835"),
        ),
        ({"model": "gpt-5.2"}, None),
        ({"model": "gpt-5-mini"}, None),
        ({"model": None}, None),
        ({"service_tier": "priority"}, None),
        ({"service_tier": None}, None),
    ],
)
def test_invalid_answers_keep_only_usage_priced_for_the_verified_model_and_tier(
    changes, expected_cost
):
    body = {**completion(), **changes}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    with pytest.raises(ProviderError, match="^SUMMARY_PROVIDER_RESPONSE_INVALID$") as error:
        OpenAI(POLICY, "synthetic-key", transport=transport).generate(MESSAGES, SCHEMA)
    billing = error.value.generation
    assert billing.cost_usd == expected_cost
    assert billing.cost_basis == ("unknown" if expected_cost is None else "token_estimate")
    assert billing.content == ""
    assert billing.prompt_tokens == 1000


@pytest.mark.parametrize(
    "failure,code,retryable,expected_cost",
    [
        (
            httpx.Response(429, text="synthetic-key private input"),
            "SUMMARY_PROVIDER_RATE_LIMIT",
            True,
            None,
        ),
        (
            httpx.Response(401, text="synthetic-key private input"),
            "SUMMARY_PROVIDER_REJECTED",
            False,
            None,
        ),
        (
            httpx.Response(503, text="synthetic-key private input"),
            "SUMMARY_PROVIDER_UNAVAILABLE",
            True,
            None,
        ),
        (
            httpx.Response(307, headers={"location": "https://example.invalid"}),
            "SUMMARY_PROVIDER_REJECTED",
            False,
            None,
        ),
        (
            httpx.Response(200, text="synthetic-key private input"),
            "SUMMARY_PROVIDER_RESPONSE_INVALID",
            False,
            None,
        ),
        (httpx.Response(200, json=[]), "SUMMARY_PROVIDER_RESPONSE_INVALID", False, None),
        (httpx.ReadTimeout("synthetic-key private input"), "SUMMARY_PROVIDER_TIMEOUT", True, None),
        (
            httpx.ConnectError("synthetic-key private input"),
            "SUMMARY_PROVIDER_UNAVAILABLE",
            True,
            None,
        ),
        (
            httpx.Response(200, json={**completion(), "error": {"message": "private input"}}),
            "SUMMARY_PROVIDER_RESPONSE_INVALID",
            False,
            Decimal("0.002835"),
        ),
        (
            httpx.Response(503, json=completion()),
            "SUMMARY_PROVIDER_UNAVAILABLE",
            True,
            Decimal("0.002835"),
        ),
    ],
)
def test_transport_failures_are_safe_and_do_not_retry(
    failure, code, retryable, expected_cost, caplog
):
    attempts = 0

    def respond(request):
        nonlocal attempts
        attempts += 1
        if isinstance(failure, Exception):
            raise failure
        return failure

    transport = httpx.MockTransport(respond)
    with pytest.raises(ProviderError) as error:
        OpenAI(POLICY, "synthetic-key", transport=transport).generate(MESSAGES, SCHEMA)
    assert error.value.code == code
    assert error.value.retryable is retryable
    assert attempts == 1
    assert str(error.value) == code
    assert "synthetic-key" not in caplog.text
    assert "private input" not in caplog.text
    if expected_cost is not None:
        assert error.value.generation.cost_usd == expected_cost
    elif error.value.generation is not None:
        assert error.value.generation.cost_usd is None


@pytest.mark.parametrize(
    "policy,key,code",
    [
        (POLICY, "", "SUMMARY_PROVIDER_NOT_CONFIGURED"),
        ({**POLICY, "input_limit_tokens": 1}, "synthetic-key", "SUMMARY_INPUT_LIMIT"),
        ({**POLICY, "max_output_tokens": 128001}, "synthetic-key", "SUMMARY_CONTEXT_LIMIT"),
    ],
)
def test_missing_credentials_or_over_budget_input_never_start_generation(policy, key, code):
    def respond(request):
        raise AssertionError("Admission failure must never send a generation request")

    with pytest.raises((BudgetError, ProviderError), match=f"^{code}$"):
        OpenAI(policy, key, transport=httpx.MockTransport(respond)).generate(MESSAGES, SCHEMA)
