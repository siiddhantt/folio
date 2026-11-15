"""Saved embedding routes govern queries independently of worker defaults."""

import json
from uuid import uuid4

import httpx
import psycopg
import pytest
from test_conversations import AnswerModel, start_chat
from test_conversations import chat_document as chat_document
from test_summaries import summary_document as summary_document

from folio.conversations.processing import process_turn


@pytest.mark.integration
def test_query_uses_direct_index_route_without_router_credentials(chat_document, monkeypatch):
    settings, client, indexes = chat_document
    # This synthetic ready index was produced in the direct embedding space.
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE document_indexes SET policy=policy || %s::jsonb WHERE id=%s",
            (json.dumps({"gateway": "openai"}), indexes[0]),
        )
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-direct")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("FOLIO_INDEX_GATEWAY", "openrouter")
    calls = []

    def respond(transport, request):
        calls.append(request)
        assert request.url.host == "api.openai.com"
        assert request.headers["authorization"] == "Bearer synthetic-direct"
        assert json.loads(request.content)["model"] == "text-embedding-3-small"
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-3-small",
                "data": [{"index": 0, "embedding": [1.0] + [0.0] * 1535}],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", respond)
    chat = start_chat(client, indexes[0])
    turn = client.post(
        f"/conversations/{chat['id']}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    assert process_turn(turn["id"], settings=settings, generator=AnswerModel()) == {
        "outcome": "ready"
    }
    trace = client.get(f"/development/conversation-turns/{turn['id']}").json()
    embedding = next(i for i in trace["invocations"] if i["stage"] == "embedding")
    assert embedding["billing_state"] == "estimated"
    assert embedding["metadata"]["gateway"] == "openai"
    assert len(calls) == 1
