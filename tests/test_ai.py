import json
from decimal import Decimal

import httpx
import pytest

from folio.ai import BudgetError, OpenRouter, ProviderError, check_budget

POLICY = {
    "model_id": "openai/gpt-5-nano",
    "provider": "openai",
    "base_url": "https://openrouter.ai/api/v1",
    "input_limit_tokens": 64000,
    "max_output_tokens": 4096,
    "token_margin": 2048,
    "reasoning_effort": "minimal",
    "timeout_seconds": 90,
}
PROFILE = {
    "model_id": "openai/gpt-5-nano",
    "provider": "openai",
    "tokenizer": "o200k_base",
    "context_tokens": 400000,
    "max_prompt_tokens": 272000,
    "max_completion_tokens": 128000,
    "input_price_per_million": "0.05",
    "output_price_per_million": "0.40",
}
MESSAGES = [{"role": "user", "content": "Evidence S1: The trial lasted six weeks."}]
SCHEMA = {
    "type": "object",
    "properties": {"overview": {"type": "string"}},
    "required": ["overview"],
    "additionalProperties": False,
}


def metadata(**route_changes):
    route = {
        "tag": "openai",
        "provider_name": "OpenAI",
        "service_tier": None,
        "status": 0,
        "context_length": 400000,
        "max_prompt_tokens": 272000,
        "max_completion_tokens": 128000,
        "pricing": {"prompt": "0.00000005", "completion": "0.0000004"},
        "supported_parameters": [
            "reasoning",
            "max_tokens",
            "response_format",
            "structured_outputs",
        ],
    }
    route.update(route_changes)
    return {"data": {"id": POLICY["model_id"], "endpoints": [route]}}


def catalog(model_id="openai/gpt-5-nano", efforts=("minimal", "low", "medium", "high")):
    return {"data": [{"id": model_id, "reasoning": {"supported_efforts": list(efforts)}}]}


def test_admission_reserves_the_verified_route_ceiling_and_counts_the_schema():
    budget = check_budget(MESSAGES, SCHEMA, POLICY, PROFILE)
    assert Decimal(budget["reservation_usd"]) == Decimal("0.0152384")
    assert budget["input_tokens_reserved"] == 272000
    assert budget["output_tokens_reserved"] == 4096
    assert budget["tokenizer"] == "o200k_base"
    assert budget["tokenizer_version"] == "0.14.0"
    larger_schema = {**SCHEMA, "description": "source " * 4000}
    with pytest.raises(BudgetError) as error:
        check_budget(MESSAGES, larger_schema, {**POLICY, "input_limit_tokens": 3000}, PROFILE)
    assert error.value.code == "SUMMARY_INPUT_LIMIT"
    with pytest.raises(BudgetError) as error:
        check_budget(
            [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}],
            SCHEMA,
            POLICY,
            PROFILE,
        )
    assert error.value.code == "SUMMARY_INPUT_INVALID"


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"max_prompt_tokens": None},
        {"max_prompt_tokens": 500000},
        {"tag": "openai/flex", "service_tier": "flex"},
        {"supported_parameters": ["response_format"]},
        {"pricing": {"prompt": "0.00000005", "completion": "0.0000004", "request": "1"}},
    ],
)
def test_only_complete_standard_route_metadata_can_admit_generation(changes):
    def respond(request):
        assert request.method == "GET"
        assert "authorization" not in request.headers
        if request.url.path == "/api/v1/models":
            return httpx.Response(200, json=catalog())
        assert request.url.path == "/api/v1/models/openai/gpt-5-nano/endpoints"
        return httpx.Response(200, json=metadata(**changes))

    client = OpenRouter(POLICY, "private-key", transport=httpx.MockTransport(respond))
    if changes:
        with pytest.raises(ProviderError) as error:
            client.profile()
        assert error.value.code == "SUMMARY_MODEL_UNAVAILABLE"
    else:
        profile = client.profile()
        assert profile["model_id"] == "openai/gpt-5-nano"
        assert profile["provider"] == "openai"
        assert profile["max_prompt_tokens"] == 272000
        assert Decimal(profile["input_price_per_million"]) == Decimal("0.05")


@pytest.mark.parametrize(
    "efforts",
    [
        ("high", "medium", "low", "minimal"),
        ("minimal", "low", "medium", "high", "xhigh"),
    ],
)
def test_effective_profile_is_stable_when_unselected_catalog_capabilities_change(efforts):
    profiles = []
    for catalog_efforts in (("minimal", "low", "medium", "high"), efforts):

        def respond(request, catalog_efforts=catalog_efforts):
            assert request.method == "GET"
            if request.url.path == "/api/v1/models":
                return httpx.Response(200, json=catalog(efforts=catalog_efforts))
            return httpx.Response(200, json=metadata())

        client = OpenRouter(POLICY, "private-key", transport=httpx.MockTransport(respond))
        profiles.append(client.profile())
    assert profiles[0]["reasoning_effort"] == "minimal"
    assert profiles[0] == profiles[1]


def test_generation_enforces_one_standard_route_and_returns_observed_usage():
    posts = []

    def respond(request):
        if request.url.path == "/api/v1/models":
            return httpx.Response(200, json=catalog())
        if request.method == "GET":
            return httpx.Response(200, json=metadata())
        posts.append(json.loads(request.content))
        assert request.url.path == "/api/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer private-key"
        return httpx.Response(
            200,
            json={
                "id": "gen-example",
                "model": "openai/gpt-5-nano",
                "provider": "OpenAI",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"overview":"Six weeks"}'}}
                ],
                "usage": {"prompt_tokens": 200, "completion_tokens": 50, "cost": 0.00003},
            },
        )

    client = OpenRouter(POLICY, "private-key", transport=httpx.MockTransport(respond))
    generation = client.generate(MESSAGES, SCHEMA)
    assert len(posts) == 1  # One billed attempt; retry ownership belongs to the workflow.
    payload = posts[0]
    assert payload["model"] == "openai/gpt-5-nano"
    assert payload["messages"] == MESSAGES
    assert payload["response_format"]["json_schema"] == {
        "name": "folio_summary",
        "strict": True,
        "schema": SCHEMA,
    }
    assert payload["max_tokens"] == 4096
    assert payload["reasoning"]["effort"] == "minimal"
    assert payload["service_tier"] == "default"
    routing = payload["provider"]
    assert routing["only"] == ["openai"]
    assert routing["allow_fallbacks"] is False
    assert routing["require_parameters"] is True
    assert routing["data_collection"] == "deny"
    assert Decimal(routing["max_price"]["prompt"]) == Decimal("0.05")
    assert Decimal(routing["max_price"]["completion"]) == Decimal("0.40")
    assert payload["transforms"] == []
    assert generation.content == '{"overview":"Six weeks"}'
    assert generation.finish_reason == "stop"
    assert (generation.prompt_tokens, generation.completion_tokens) == (200, 50)
    assert generation.cost_usd == Decimal("0.00003")
    assert (generation.model, generation.provider) == ("openai/gpt-5-nano", "openai")


@pytest.mark.parametrize(
    "model_id,efforts,allowed",
    [
        ("openai/gpt-5-mini", ("minimal", "low", "medium", "high"), True),
        ("openai/gpt-5.1", ("none", "low", "medium", "high"), False),
    ],
)
def test_configured_mapped_model_uses_its_own_verified_limits_and_prices(
    model_id, efforts, allowed
):
    policy = {**POLICY, "model_id": model_id}

    def respond(request):
        if request.url.path == "/api/v1/models":
            return httpx.Response(200, json=catalog(model_id, efforts))
        if request.method == "GET":
            assert request.url.path == f"/api/v1/models/{model_id}/endpoints"
            body = metadata(pricing={"prompt": "0.00000025", "completion": "0.000002"})
            body["data"]["id"] = model_id
            return httpx.Response(200, json=body)
        assert json.loads(request.content)["model"] == model_id
        return httpx.Response(
            200,
            json={
                "model": model_id,
                "provider": "OpenAI",
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
            },
        )

    client = OpenRouter(policy, "private-key", transport=httpx.MockTransport(respond))
    if not allowed:
        with pytest.raises(ProviderError) as error:
            client.generate(MESSAGES, SCHEMA)
        assert error.value.code == "SUMMARY_MODEL_UNAVAILABLE"
        return
    profile = client.profile()
    budget = check_budget(MESSAGES, SCHEMA, policy, profile)
    assert budget["tokenizer"] == "o200k_base"
    assert Decimal(budget["reservation_usd"]) == Decimal("0.076192")
    assert client.generate(MESSAGES, SCHEMA).model == model_id


@pytest.mark.parametrize(
    "message,finish,expected",
    [
        ({"content": "partial"}, "length", "length"),
        ({"content": None, "refusal": "private refusal text"}, "stop", "refusal"),
    ],
)
def test_unsuccessful_completions_preserve_billing_metadata(message, finish, expected):
    def respond(request):
        if request.url.path == "/api/v1/models":
            return httpx.Response(200, json=catalog())
        if request.method == "GET":
            return httpx.Response(200, json=metadata())
        return httpx.Response(
            200,
            json={
                "model": "openai/gpt-5-nano",
                "provider": "OpenAI",
                "choices": [{"finish_reason": finish, "message": message}],
                "usage": {"prompt_tokens": 200, "completion_tokens": 4096, "cost": 0.0016484},
            },
        )

    client = OpenRouter(POLICY, "private-key", transport=httpx.MockTransport(respond))
    result = client.generate(MESSAGES, SCHEMA)
    assert result.finish_reason == expected
    assert result.completion_tokens == 4096
    assert result.cost_usd == Decimal("0.0016484")
    assert "private refusal text" not in result.content


@pytest.mark.parametrize(
    "policy,profile_changes,code",
    [
        ({**POLICY, "input_limit_tokens": 10}, {}, "SUMMARY_INPUT_LIMIT"),
        (POLICY, {"max_completion_tokens": 100}, "SUMMARY_CONTEXT_LIMIT"),
        (
            POLICY,
            {"context_length": 4200, "max_prompt_tokens": 2000, "max_completion_tokens": 4096},
            "SUMMARY_CONTEXT_LIMIT",
        ),
        ({**POLICY, "model_id": "openai/gpt-6-luna"}, {}, "SUMMARY_MODEL_UNAVAILABLE"),
    ],
)
def test_invalid_input_or_model_limits_never_start_a_paid_request(policy, profile_changes, code):
    def respond(request):
        assert request.method == "GET", "A rejected input must never start paid generation"
        if request.url.path == "/api/v1/models":
            return httpx.Response(200, json=catalog())
        return httpx.Response(200, json=metadata(**profile_changes))

    with pytest.raises((BudgetError, ProviderError)) as error:
        client = OpenRouter(policy, "private-key", transport=httpx.MockTransport(respond))
        client.generate(MESSAGES, SCHEMA)
    assert error.value.code == code


@pytest.mark.parametrize(
    "failure,code,retryable",
    [
        (
            httpx.Response(429, text="private-key document secret"),
            "SUMMARY_PROVIDER_RATE_LIMIT",
            True,
        ),
        (
            httpx.Response(401, text="private-key document secret"),
            "SUMMARY_PROVIDER_REJECTED",
            False,
        ),
        (
            httpx.Response(503, text="private-key document secret"),
            "SUMMARY_PROVIDER_UNAVAILABLE",
            True,
        ),
        (httpx.ReadTimeout("private-key document secret"), "SUMMARY_PROVIDER_TIMEOUT", True),
        (
            httpx.Response(200, json={"choices": [], "usage": {"cost": 0.001}}),
            "SUMMARY_PROVIDER_RESPONSE_INVALID",
            False,
        ),
    ],
)
def test_transport_failures_are_safe_and_do_not_retry(failure, code, retryable, caplog):
    attempts = 0

    def respond(request):
        nonlocal attempts
        if request.url.path == "/api/v1/models":
            return httpx.Response(200, json=catalog())
        if request.method == "GET":
            return httpx.Response(200, json=metadata())
        attempts += 1
        if isinstance(failure, Exception):
            raise failure
        return failure

    client = OpenRouter(POLICY, "private-key", transport=httpx.MockTransport(respond))
    with pytest.raises(ProviderError) as error:
        client.generate(MESSAGES, SCHEMA)
    assert error.value.code == code
    assert error.value.retryable is retryable
    assert attempts == 1
    assert str(error.value) == code
    assert "private-key" not in caplog.text
    assert "document secret" not in caplog.text
