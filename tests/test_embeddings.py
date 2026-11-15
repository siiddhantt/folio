from decimal import Decimal

import httpx
import pytest

from folio.indexing.provider import EmbeddingError, OpenRouterEmbeddings

POLICY = {
    "model_id": "openai/text-embedding-3-small",
    "provider": "openai",
    "dimensions": 1536,
    "input_price_per_million": "0.02",
    "timeout_seconds": 30,
}


def test_embeddings_follow_response_indices_and_keep_billing_metadata():
    def respond(request):
        assert request.url.path == "/api/v1/embeddings"
        return httpx.Response(
            200,
            json={
                "model": "openai/text-embedding-3-small",
                "object": "list",
                "id": "embedding-1",
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0] + [0.0] * 1534},
                    {"index": 0, "embedding": [1.0] + [0.0] * 1535},
                ],
                "usage": {"prompt_tokens": 12, "total_tokens": 12, "cost": 0.00000024},
            },
        )

    client = OpenRouterEmbeddings(POLICY, "synthetic-key", transport=httpx.MockTransport(respond))
    result = client.embed(["First passage", "Second passage"])
    assert result.vectors[0][:2] == [1.0, 0.0]
    assert result.vectors[1][:2] == [0.0, 1.0]
    assert result.cost_usd == Decimal("0.00000024")
    assert result.metadata["response_id"] == "embedding-1"


@pytest.mark.parametrize(
    "data",
    [
        [{"index": 0, "embedding": [1.0]}],
        [{"index": 0, "embedding": [0.0] * 1536}],
        [{"embedding": [1.0] + [0.0] * 1535}],
    ],
)
def test_invalid_vectors_are_rejected_without_erasing_the_charge(data):
    response = {
        "model": POLICY["model_id"],
        "data": data,
        "usage": {"prompt_tokens": 4, "total_tokens": 4, "cost": 0.00000008},
    }
    client = OpenRouterEmbeddings(
        POLICY,
        "synthetic-key",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )
    with pytest.raises(EmbeddingError) as failure:
        client.embed(["A passage"])
    assert failure.value.code == "EMBEDDING_RESPONSE_INVALID"
    assert failure.value.cost_usd == Decimal("0.00000008")
    assert not failure.value.retryable


def test_index_configuration_only_depends_on_shared_allowances_not_summary_options(monkeypatch):
    from folio.config import Settings
    from folio.indexing.config import capture_policy

    monkeypatch.setenv("FOLIO_INDEX_ENABLED", "true")
    monkeypatch.setenv("FOLIO_SUMMARY_ENABLED", "false")
    monkeypatch.setenv("FOLIO_SUMMARY_TIMEOUT_SECONDS", "invalid")
    monkeypatch.setenv("FOLIO_SUMMARY_BUDGET_USD", "0.75")
    policy = capture_policy(Settings(_env_file=None))
    assert policy["enabled"]
    assert policy["budget_usd"] == "0.75"


def test_direct_embeddings_use_native_endpoint_and_estimate_reported_usage(monkeypatch):
    import json

    from folio.indexing.provider import embedding_client

    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-direct")

    def respond(request):
        assert str(request.url) == "https://api.openai.com/v1/embeddings"
        assert request.headers["authorization"] == "Bearer synthetic-direct"
        payload = json.loads(request.content)
        assert payload["model"] == "text-embedding-3-small"
        assert payload["dimensions"] == 1536
        assert "provider" not in payload
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-3-small",
                "data": [{"index": 0, "embedding": [1.0] + [0.0] * 1535}],
                "usage": {"prompt_tokens": 12, "total_tokens": 12},
            },
        )

    client = embedding_client(
        {**POLICY, "gateway": "openai"}, transport=httpx.MockTransport(respond)
    )
    assert client.profile()["input_price_per_million"] == "0.02"
    result = client.embed(["A passage"])
    assert result.cost_usd == Decimal("0.00000024")
    assert result.metadata["cost_basis"] == "token_estimate"
    assert result.metadata["gateway"] == "openai"


def test_legacy_index_policy_keeps_openrouter_even_when_direct_default_changes(monkeypatch):
    from folio.indexing.provider import embedding_client

    monkeypatch.setenv("FOLIO_INDEX_GATEWAY", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-direct")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-router")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": POLICY["model_id"],
                "data": [{"index": 0, "embedding": [1.0] + [0.0] * 1535}],
                "usage": {"cost": 0.00000008},
            },
        )

    embedding_client(POLICY, transport=httpx.MockTransport(respond)).embed(["Query"])
    assert requests[0].url.host == "openrouter.ai"
    assert requests[0].headers["authorization"] == "Bearer synthetic-router"


@pytest.mark.parametrize(
    "usage",
    [
        {},
        {"prompt_tokens": True, "total_tokens": 1},
        {"prompt_tokens": 3, "total_tokens": 2},
        {"prompt_tokens": -1, "total_tokens": -1},
    ],
)
def test_direct_embeddings_do_not_invent_missing_or_invalid_costs(usage):
    from folio.indexing.provider import OpenAIEmbeddings

    client = OpenAIEmbeddings(
        {**POLICY, "gateway": "openai"},
        "synthetic",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "model": "text-embedding-3-small",
                    "usage": usage,
                    "data": [{"index": 0, "embedding": [1.0] + [0.0] * 1535}],
                },
            )
        ),
    )
    result = client.embed(["Query"])
    assert result.cost_usd is None
    assert result.metadata["cost_basis"] == "unknown"
