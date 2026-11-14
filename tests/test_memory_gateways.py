import json
from decimal import Decimal

import httpx
import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_ai import catalog, metadata
from test_conversation_memory import long_chat as long_chat
from test_conversations import QueryEmbedding
from test_conversations import chat_document as chat_document
from test_summaries import summary_document as summary_document

from folio.conversations.config import ChatSettings
from folio.conversations.memory.dispatcher import dispatch_once
from folio.conversations.memory.processing import process_memory


@pytest.mark.integration
def test_direct_memory_does_not_spend_when_next_question_cannot_embed(long_chat, monkeypatch):
    settings, client, _, _, turns = long_chat
    for prefix in ("FOLIO_CHAT_", "FOLIO_CHAT_REWRITE_", "FOLIO_MEMORY_"):
        monkeypatch.setenv(prefix + "GATEWAY", "openai")
        monkeypatch.setenv(prefix + "MODEL_ID", "openai/gpt-5.2")
        monkeypatch.setenv(prefix + "REASONING_EFFORT", "none")
    monkeypatch.setenv("OPENAI_API_KEY", "direct-fixture")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE conversation_turns SET policy=%s WHERE id=%s",
            (Jsonb(ChatSettings().policy(settings)), turns[-1]["id"]),
        )
    memory_id = dispatch_once(settings)[0]["memory_id"]

    def no_network(transport, request):
        raise AssertionError("Missing credentials must be caught before provider requests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
    result = process_memory(memory_id, settings=settings)
    assert result["code"] == "MEMORY_PROVIDER_NOT_CONFIGURED"
    trace = client.get(f"/development/conversation-memories/{memory_id}").json()
    assert trace["attempts"] == []


@pytest.mark.integration
def test_memory_keeps_its_service_and_leaves_headroom_at_foreground_prices(long_chat, monkeypatch):
    settings, client, _, _, turns = long_chat
    for name, value in {
        "FOLIO_CHAT_GATEWAY": "openrouter",
        "FOLIO_CHAT_MODEL_ID": "openai/gpt-5.2",
        "FOLIO_CHAT_REASONING_EFFORT": "none",
        "FOLIO_CHAT_REWRITE_GATEWAY": "openrouter",
        "FOLIO_CHAT_REWRITE_MODEL_ID": "openai/gpt-5.2",
        "FOLIO_CHAT_REWRITE_REASONING_EFFORT": "none",
        "FOLIO_MEMORY_GATEWAY": "openai",
        "FOLIO_MEMORY_MODEL_ID": "openai/gpt-5.2",
        "FOLIO_MEMORY_REASONING_EFFORT": "none",
        "OPENAI_API_KEY": "direct-fixture",
        "OPENROUTER_API_KEY": "router-fixture",
    }.items():
        monkeypatch.setenv(name, value)
    # Give this synthetic transcript the selected policy before the background planner runs.
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE conversation_turns SET policy=%s WHERE id=%s",
            (Jsonb(ChatSettings().policy(settings)), turns[-1]["id"]),
        )
    memory_id = dispatch_once(settings)[0]["memory_id"]
    url = f"/development/conversation-memories/{memory_id}"
    saved = client.get(url).json()["memory"]
    assert saved["policy"]["base_url"] == "https://api.openai.com/v1"
    assert saved["policy"]["foreground_policy"]["base_url"] == "https://openrouter.ai/api/v1"
    monkeypatch.setenv("FOLIO_MEMORY_GATEWAY", "openrouter")
    requests = []

    def respond(transport, request):
        requests.append((request.method, request.url.host))
        if request.method == "GET":
            assert request.url.host == "openrouter.ai"
            if request.url.path.endswith("/endpoints"):
                # Synthetic cheaper foreground route: reusing direct prices would exceed $0.10.
                body = metadata()
                body["data"]["id"] = "openai/gpt-5.2"
            else:
                body = catalog("openai/gpt-5.2", efforts=("none",))
            return httpx.Response(200, json=body)
        assert request.url.host == "api.openai.com"
        assert request.headers["Authorization"] == "Bearer direct-fixture"
        payload = json.loads(request.content)
        assert payload["response_format"]["json_schema"]["name"] == "folio_memory"
        source = json.loads(payload["messages"][1]["content"])
        notes = {
            "notes": [
                {
                    "text": "The user is tracking the warehouse delivery date in May.",
                    "turn_ids": [source["history"][0]["turn_id"]],
                }
            ]
        }
        return httpx.Response(
            200,
            json={
                "id": "memory-fixture",
                "model": "gpt-5.2-2025-12-11",
                "service_tier": "default",
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(notes)}}],
                "usage": {
                    "prompt_tokens": 250,
                    "completion_tokens": 60,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            },
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", respond)
    assert process_memory(memory_id, settings=settings, embedder=QueryEmbedding()) == {
        "outcome": "ready"
    }
    trace = client.get(url).json()
    assert trace["memory"]["result"]["notes"][0]["turn_ids"] == [turns[0]["id"]]
    assert trace["attempts"][0]["billing_state"] == "estimated"
    assert Decimal(str(trace["attempts"][0]["reserved_usd"])) == Decimal("0.014336")
    assert ("GET", "openrouter.ai") in requests
    assert requests.count(("POST", "api.openai.com")) == 1
