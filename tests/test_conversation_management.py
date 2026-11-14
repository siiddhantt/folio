import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from test_conversations import AnswerModel, QueryEmbedding, start_chat
from test_conversations import chat_document as chat_document
from test_summaries import summary_document as summary_document

from folio.conversations.processing import process_turn


@pytest.mark.integration
def test_first_answer_saves_its_generated_title_in_the_same_call(chat_document):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}"
    submitted = client.post(
        f"{url}/turns",
        json={"question": "When does the project begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()

    class TitledAnswer(AnswerModel):
        def generate(self, messages, schema, **kwargs):
            assert "title" in schema["properties"]
            result = super().generate(messages, schema, **kwargs)
            result.content = json.dumps(
                json.loads(result.content) | {"title": "Project start date"}
            )
            return result

    model = TitledAnswer()
    assert process_turn(
        submitted["id"], settings=settings, embedder=QueryEmbedding(), generator=model
    ) == {"outcome": "ready"}
    saved = client.get(url).json()
    assert saved["title"] == "Project start date"
    assert saved["title_source"] == "generated" and saved["title_version"] == 0
    assert saved["state"] == "ready"
    assert client.get("/conversations").json()["items"][0]["title"] == "Project start date"
    assert len(model.calls) == 1


@pytest.mark.integration
def test_manual_rename_wins_while_first_answer_is_running(chat_document):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}"
    submitted = client.post(
        f"{url}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()

    class RenameWhileAnswering(AnswerModel):
        def generate(self, messages, schema, **kwargs):
            renamed = client.patch(url, json={"title": "My project notes", "expected_version": 0})
            assert renamed.status_code == 200
            result = super().generate(messages, schema, **kwargs)
            result.content = json.dumps(
                json.loads(result.content) | {"title": "Project start date"}
            )
            return result

    assert process_turn(
        submitted["id"],
        settings=settings,
        embedder=QueryEmbedding(),
        generator=RenameWhileAnswering(),
    ) == {"outcome": "ready"}
    saved = client.get(url).json()
    assert saved["title"] == "My project notes"
    assert saved["title_source"] == "manual" and saved["title_version"] == 1
    assert saved["state"] == "ready"
    stale = client.patch(url, json={"title": "Older tab title", "expected_version": 0})
    assert stale.status_code == 409
    assert client.get(url).json()["title"] == "My project notes"


@pytest.mark.integration
def test_delete_pending_chat_hides_reads_and_keeps_replay_and_cursor_identity(chat_document):
    settings, client, indexes = chat_document
    older = start_chat(client, indexes[0])
    creation_key = {"Idempotency-Key": str(uuid4())}
    chat = client.post("/conversations", json={"index_id": indexes[0]}, headers=creation_key).json()
    url = f"/conversations/{chat['id']}"
    turn = client.post(
        f"{url}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 204
    for endpoint in (
        url,
        f"{url}/turns",
        f"{url}/turns/{turn['id']}",
        f"/development/conversation-turns/{turn['id']}",
    ):
        assert client.get(endpoint).status_code == 404
    assert (
        client.patch(url, json={"title": "Bring it back", "expected_version": 0}).status_code == 404
    )
    assert (
        client.post(
            f"{url}/turns",
            json={"question": "Another question"},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/conversations", json={"index_id": indexes[0]}, headers=creation_key
        ).status_code
        == 410
    )
    assert [item["id"] for item in client.get("/conversations").json()["items"]] == [older["id"]]
    assert client.get(f"/conversations?before={chat['id']}").json()["items"][0]["id"] == older["id"]
    embedding, model = QueryEmbedding(), AnswerModel()
    assert process_turn(turn["id"], settings=settings, embedder=embedding, generator=model) == {
        "outcome": "ignored"
    }
    assert not embedding.calls and not model.calls


@pytest.mark.integration
def test_two_manual_renames_cannot_silently_overwrite_each_other(chat_document):
    _, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda title: client.patch(url, json={"title": title, "expected_version": 0}),
                ["First tab title", "Second tab title"],
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert client.get(url).json()["title"] == winner["title"]
    assert winner["title_version"] == 1


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["embedding", "answer", "unknown_answer"])
def test_delete_during_paid_work_retains_billing_without_publishing(chat_document, stage):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}"
    turn = client.post(
        f"{url}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    observed = {}

    def delete():
        observed["held"] = client.get("/development/settings").json()["runtime"]["held_usd"]
        assert client.delete(url).status_code == 204
        assert client.get(url).status_code == 404

    class DeletingEmbedding(QueryEmbedding):
        def embed(self, texts):
            if stage == "embedding":
                delete()
            return super().embed(texts)

    class DeletingAnswer(AnswerModel):
        def generate(self, messages, schema, **kwargs):
            delete()
            result = super().generate(messages, schema, **kwargs)
            if stage == "unknown_answer":
                raise TimeoutError("Controlled unknown provider outcome")
            result.content = json.dumps(json.loads(result.content) | {"title": "Late answer title"})
            return result

    model = DeletingAnswer()
    assert (
        process_turn(turn["id"], settings=settings, embedder=DeletingEmbedding(), generator=model)[
            "outcome"
        ]
        == "superseded"
    )
    runtime = client.get("/development/settings").json()["runtime"]
    expected_spend = "0.0000421" if stage == "answer" else "0.0000001"
    assert Decimal(runtime["spent_usd"]) == Decimal(expected_spend)
    if stage == "unknown_answer":
        assert Decimal(runtime["held_usd"]) == Decimal(observed["held"]) > 0
    else:
        assert Decimal(runtime["held_usd"]) == 0
    assert client.get(f"{url}/turns/{turn['id']}").status_code == 404
    assert client.get(f"/development/conversation-turns/{turn['id']}").status_code == 404
    # Retention and stale-publication are internal persistence contracts, distinct
    # from the public read routes intentionally hiding the deleted conversation.
    with psycopg.connect(settings.database_url) as conn:
        retained = conn.execute(
            "SELECT c.deleted_at,c.title,t.question,t.result FROM conversations c "
            "JOIN conversation_turns t ON t.conversation_id=c.id WHERE t.id=%s",
            (turn["id"],),
        ).fetchone()
        assert retained[0] is not None and retained[1] is None
        assert retained[2] == "When does it begin?" and retained[3] is None
    assert process_turn(
        turn["id"], settings=settings, embedder=QueryEmbedding(), generator=model
    ) == {"outcome": "ignored"}
    if stage == "embedding":
        assert not model.calls


@pytest.mark.integration
@pytest.mark.parametrize("legacy", [True, False])
def test_legacy_policy_and_invalid_title_keep_a_readable_fallback(chat_document, legacy):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}"
    assert chat["title"] == chat["document_name"]
    turn = client.post(
        f"{url}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    if legacy:
        with psycopg.connect(settings.database_url) as conn:
            conn.execute(
                "UPDATE conversation_turns SET policy=policy || "
                '\'{"prompt_version":1,"schema_version":1}\'::jsonb WHERE id=%s',
                (turn["id"],),
            )

    class TitleContract(AnswerModel):
        def generate(self, messages, schema, **kwargs):
            assert ("title" in schema["properties"]) is not legacy
            result = super().generate(messages, schema, **kwargs)
            if not legacy:
                result.content = json.dumps(json.loads(result.content) | {"title": "x" * 61})
            return result

    assert process_turn(
        turn["id"], settings=settings, embedder=QueryEmbedding(), generator=TitleContract()
    ) == {"outcome": "ready"}
    saved = client.get(url).json()
    assert saved["title"] == "When does it begin?"
    assert saved["title_source"] is None and saved["title_version"] == 0


@pytest.mark.integration
@pytest.mark.parametrize("bad_title", ["Garage\x00coverage", "Garage\ud800coverage"])
def test_unstorable_generated_title_keeps_valid_answer(chat_document, bad_title):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}"
    turn = client.post(
        f"{url}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()

    class UnstorableTitle(AnswerModel):
        def generate(self, messages, schema, **kwargs):
            result = super().generate(messages, schema, **kwargs)
            result.content = json.dumps(json.loads(result.content) | {"title": bad_title})
            return result

    assert process_turn(
        turn["id"], settings=settings, embedder=QueryEmbedding(), generator=UnstorableTitle()
    ) == {"outcome": "ready"}
    assert client.get(url).json()["title"] == "When does it begin?"


@pytest.mark.integration
@pytest.mark.parametrize("bad_title", ["Garage\x00coverage", "Garage\ud800coverage"])
def test_unstorable_manual_title_is_rejected_as_input(chat_document, bad_title):
    _, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    response = client.patch(
        f"/conversations/{chat['id']}",
        content=json.dumps({"title": bad_title, "expected_version": 0}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert client.get(f"/conversations/{chat['id']}").json()["title_version"] == 0
