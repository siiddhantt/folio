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
