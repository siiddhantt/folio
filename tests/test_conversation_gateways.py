import json
from uuid import uuid4

import httpx
import pytest
from test_conversations import QueryEmbedding, start_chat
from test_conversations import chat_document as chat_document
from test_summaries import summary_document as summary_document

from folio.conversations.processing import process_turn


@pytest.fixture
def direct_chat(chat_document, monkeypatch):
    for key, value in {
        "FOLIO_CHAT_GATEWAY": "openai",
        "FOLIO_CHAT_MODEL_ID": "openai/gpt-5.2",
        "FOLIO_CHAT_REASONING_EFFORT": "none",
        "FOLIO_CHAT_REWRITE_GATEWAY": "openai",
        "FOLIO_CHAT_REWRITE_MODEL_ID": "openai/gpt-5.2",
        "FOLIO_CHAT_REWRITE_REASONING_EFFORT": "none",
        "OPENAI_API_KEY": "direct-fixture",
        "OPENROUTER_API_KEY": "router-fixture",
    }.items():
        monkeypatch.setenv(key, value)
    return chat_document


@pytest.mark.integration
def test_direct_answer_and_followup_keep_index_route_and_saved_service(direct_chat, monkeypatch):
    settings, client, indexes = direct_chat
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    requests = []

    def respond(transport, request):
        if request.method == "GET":
            assert request.url.host == "openrouter.ai"
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "openai/text-embedding-3-small",
                        "endpoints": [
                            {
                                "tag": "openai",
                                "status": 0,
                                "context_length": 8192,
                                "pricing": {"prompt": "0.00000002"},
                            }
                        ],
                    }
                },
            )
        payload = json.loads(request.content)
        requests.append((request.url.host, payload))
        if request.url.path.endswith("/embeddings"):
            assert request.url.host == "openrouter.ai"
            assert request.headers["Authorization"] == "Bearer router-fixture"
            return httpx.Response(
                200,
                json={
                    "id": "embed",
                    "model": "openai/text-embedding-3-small",
                    "data": [{"index": 0, "embedding": [1.0] + [0.0] * 1535}],
                    "usage": {"prompt_tokens": 5, "cost": 0.0000001},
                },
            )
        assert request.url.host == "api.openai.com"
        assert request.headers["Authorization"] == "Bearer direct-fixture"
        name = payload["response_format"]["json_schema"]["name"]
        content = (
            {
                "kind": "document_query",
                "query": "Does it begin in May?",
                "response": None,
                "turn_ids": [],
            }
            if name == "folio_question"
            else {
                "outcome": "answer",
                "statements": [{"text": "It begins in May.", "source_ids": ["S1"]}],
            }
        )
        if "title" in payload["response_format"]["json_schema"]["schema"]["properties"]:
            content["title"] = "Start date"
        return httpx.Response(
            200,
            json={
                "id": "answer",
                "model": "gpt-5.2-2025-12-11",
                "service_tier": "default",
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}],
                "usage": {
                    "prompt_tokens": 200,
                    "completion_tokens": 40,
                    "prompt_tokens_details": {"cached_tokens": 100},
                },
            },
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", respond)
    for sequence, question in enumerate(("When does it begin?", "Is that May?")):
        submitted = client.post(
            url,
            json={"question": question, "observed_head": sequence},
            headers={"Idempotency-Key": str(uuid4())},
        ).json()
        # Changing the worker environment must not reroute an already accepted question.
        monkeypatch.setenv("FOLIO_CHAT_GATEWAY", "openrouter")
        monkeypatch.setenv("FOLIO_CHAT_REWRITE_GATEWAY", "openrouter")
        assert process_turn(submitted["id"], settings=settings) == {"outcome": "ready"}
        saved = client.get(f"{url}/{submitted['id']}").json()
        assert saved["citations"][0]["text"] == "The project begins in May."
        assert saved["answer"]["statements"][0]["text"] == "It begins in May."
        trace = client.get(f"/development/conversation-turns/{submitted['id']}").json()
        answer = next(item for item in trace["invocations"] if item["stage"] == "answer")
        assert answer["billing_state"] == "estimated"
        assert answer["metadata"]["cost_basis"] == "token_estimate"
        monkeypatch.setenv("FOLIO_CHAT_GATEWAY", "openai")
        monkeypatch.setenv("FOLIO_CHAT_REWRITE_GATEWAY", "openai")
    assert len(client.get(url).json()["items"]) == 2
    assert [host for host, _ in requests].count("api.openai.com") == 3
    assert [host for host, _ in requests].count("openrouter.ai") == 2


@pytest.mark.integration
def test_missing_selected_answer_key_fails_before_embedding(direct_chat, monkeypatch):
    settings, client, indexes = direct_chat
    chat = start_chat(client, indexes[0])
    submitted = client.post(
        f"/conversations/{chat['id']}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    monkeypatch.setenv("OPENAI_API_KEY", "")
    embedding = QueryEmbedding()
    result = process_turn(submitted["id"], settings=settings, embedder=embedding)
    assert result["code"] == "CHAT_PROVIDER_NOT_CONFIGURED"
    assert embedding.calls == []
    trace = client.get(f"/development/conversation-turns/{submitted['id']}").json()
    assert trace["invocations"] == []
