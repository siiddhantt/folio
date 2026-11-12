import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from test_summaries import Model
from test_summaries import summary_document as summary_document


class AnswerModel(Model):
    def generate(self, messages, schema, **kwargs):
        self.calls.append(messages)
        return SimpleNamespace(
            content=json.dumps(
                {
                    "outcome": "answer",
                    "statements": [{"text": "It begins in May.", "source_ids": ["S1"]}],
                }
            ),
            finish_reason="stop",
            prompt_tokens=200,
            completion_tokens=80,
            cost_usd=Decimal("0.000042"),
            response_id="answer-fixture",
            model="openai/gpt-5-nano",
            provider="openai",
        )


class QueryEmbedding:
    def __init__(self):
        self.calls = []

    def profile(self):
        return {
            "model_id": "openai/text-embedding-3-small",
            "provider": "openai",
            "dimensions": 1536,
            "max_input_tokens": 8192,
            "input_price_per_million": "0.02",
        }

    def embed(self, texts):
        self.calls.append(texts)
        return SimpleNamespace(
            vectors=[[1.0] + [0.0] * 1535],
            cost_usd=Decimal("0.0000001"),
            metadata={"prompt_tokens": 5, "response_id": "embedding-fixture"},
        )


@pytest.fixture
def chat_document(summary_document, monkeypatch):
    settings, client, publish = summary_document
    monkeypatch.setenv("FOLIO_CHAT_MODEL_ID", "openai/gpt-5-nano")
    monkeypatch.setenv("FOLIO_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("FOLIO_CHAT_REASONING_EFFORT", "minimal")
    indexes = []
    for other in (False, True):
        _, revision = publish()
        with psycopg.connect(settings.database_url) as conn:
            index = conn.execute(
                "UPDATE document_indexes SET state='ready',chunk_count=1 WHERE "
                "revision_id=%s RETURNING id",
                (revision,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO "
                "index_chunks(index_id,revision_id,ordinal,batch_no,text,tokens,sha256,embedding)"
                " "
                "VALUES (%s,%s,1,1,%s,10,%s,%s::vector)",
                (
                    index,
                    revision,
                    "OTHER_DOCUMENT_SENTINEL" if other else "The project begins in May.",
                    "a" * 64,
                    json.dumps([1.0] + [0.0] * 1535),
                ),
            )
            conn.execute(
                "INSERT INTO chunk_sources VALUES (%s,%s,1,0,'first','body')", (index, revision)
            )
            indexes.append(str(index))
    return settings, client, indexes


def start_chat(client, index):
    response = client.post(
        "/conversations", json={"index_id": index}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.integration
def test_first_answer_is_scoped_cited_and_readable_after_reload(chat_document):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    submitted = client.post(
        url, json={"question": "When does it begin?"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert submitted.status_code == 202
    turn = submitted.json()
    assert turn["state"] == "pending"
    assert client.get(url).json()["items"][0]["question"] == "When does it begin?"

    from folio.conversations.processing import process_turn

    embedding, model = QueryEmbedding(), AnswerModel()
    assert process_turn(turn["id"], settings=settings, embedder=embedding, generator=model) == {
        "outcome": "ready"
    }
    saved = client.get(f"{url}/{turn['id']}").json()
    assert saved["answer"]["statements"] == [{"text": "It begins in May.", "source_ids": ["S1"]}]
    assert saved["citations"][0]["pages"] == [1]
    assert saved["citations"][0]["text"] == "The project begins in May."
    assert "OTHER_DOCUMENT_SENTINEL" not in json.dumps(model.calls)
    assert client.get(url).json()["items"] == [saved]
    assert client.get("/conversations").json()["items"][0]["id"] == chat["id"]
    assert client.get(f"/conversations/{chat['id']}").json()["state"] == "ready"
    assert process_turn(turn["id"], settings=settings, embedder=embedding, generator=model) == {
        "outcome": "ignored"
    }
    assert len(model.calls) == len(embedding.calls) == 1


@pytest.mark.integration
def test_submission_replay_and_stale_head_are_explicit(chat_document):
    settings, client, indexes = chat_document
    key = {"Idempotency-Key": str(uuid4())}
    chat = client.post("/conversations", json={"index_id": indexes[0]}, headers=key).json()
    assert client.post("/conversations", json={"index_id": indexes[0]}, headers=key).json() == chat
    assert (
        client.post("/conversations", json={"index_id": indexes[1]}, headers=key).status_code == 409
    )
    url = f"/conversations/{chat['id']}/turns"
    response = client.post(url, json={"question": "When does it begin?"}, headers=key)
    assert response.status_code == 202
    from folio.conversations.processing import process_turn

    process_turn(
        response.json()["id"], settings=settings, embedder=QueryEmbedding(), generator=AnswerModel()
    )
    replay = client.post(url, json={"question": "When does it begin?"}, headers=key)
    assert replay.json()["id"] == response.json()["id"]
    assert replay.json()["state"] == "ready"
    assert client.post(url, json={"question": "Changed"}, headers=key).status_code == 409
    assert (
        client.post(
            url, json={"question": "Another question"}, headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 409
    )
    assert len(client.get(url).json()["items"]) == 1


@pytest.mark.integration
@pytest.mark.parametrize("failure", ["citation", "truncated"])
def test_invalid_answer_stays_failed_with_bill_and_question_preserved(chat_document, failure):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    turn = client.post(
        url, json={"question": "When does it begin?"}, headers={"Idempotency-Key": str(uuid4())}
    ).json()

    class Invalid(AnswerModel):
        def generate(self, *args, **kwargs):
            result = super().generate(*args, **kwargs)
            if failure == "citation":
                result.content = result.content.replace('"S1"', '"OTHER"')
            else:
                result.finish_reason = "length"
            return result

    from folio.conversations.processing import process_turn

    result = process_turn(
        turn["id"], settings=settings, embedder=QueryEmbedding(), generator=Invalid()
    )
    assert result["outcome"] == "failed"
    saved = client.get(f"{url}/{turn['id']}").json()
    assert saved["answer"] is None and saved["citations"] == []
    assert saved["error"]["code"] == (
        "CHAT_OUTPUT_INCOMPLETE" if failure == "truncated" else "CHAT_OUTPUT_INVALID"
    )
    assert saved["question"] == "When does it begin?"
    trace = client.get(f"/development/conversation-turns/{turn['id']}")
    assert trace.status_code == 200
    assert trace.json()["attempts"][0]["error_code"]
    assert Decimal(str(trace.json()["invocations"][-1]["cost_usd"])) == Decimal("0.000042")
    assert Decimal(client.get("/development/settings").json()["runtime"]["spent_usd"]) == Decimal(
        "0.0000421"
    )


@pytest.mark.integration
@pytest.mark.parametrize("interruption", ["timeout", "worker_lost"])
def test_recovery_reuses_embedding_and_keeps_uncertain_or_late_bills(chat_document, interruption):
    from folio.conversations.lifecycle import recover_expired
    from folio.conversations.processing import process_turn
    from folio.database import Database

    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    turn = client.post(
        url, json={"question": "When does it begin?"}, headers={"Idempotency-Key": str(uuid4())}
    ).json()

    class Interrupted(AnswerModel):
        def generate(self, *args, **kwargs):
            result = super().generate(*args, **kwargs)
            if interruption == "timeout":
                raise TimeoutError("Provider did not respond")
            with psycopg.connect(settings.database_url) as conn:
                conn.execute(
                    "UPDATE conversation_turns SET lease_expires_at=now()-interval '1 second' "
                    "WHERE id=%s",
                    (turn["id"],),
                )
            database = Database(settings.database_url)
            database.open()
            try:
                assert recover_expired(database) == 1
            finally:
                database.close()
            return result

    embedding = QueryEmbedding()
    result = process_turn(
        turn["id"], settings=settings, embedder=embedding, generator=Interrupted()
    )
    assert result["outcome"] == ("pending" if interruption == "timeout" else "superseded")
    saved = client.get(f"{url}/{turn['id']}").json()
    assert saved["state"] == "pending" and saved["answer"] is None
    trace_url = f"/development/conversation-turns/{turn['id']}"
    first = client.get(trace_url).json()["invocations"][-1]
    assert first["billing_state"] == ("unknown" if interruption == "timeout" else "known")
    if interruption == "worker_lost":
        assert Decimal(str(first["cost_usd"])) == Decimal("0.000042")
    else:
        assert first["cost_usd"] is None and Decimal(str(first["reserved_usd"])) > 0

    with psycopg.connect(settings.database_url) as conn:
        conn.execute("UPDATE conversation_turns SET available_at=now() WHERE id=%s", (turn["id"],))
    assert (
        process_turn(turn["id"], settings=settings, embedder=embedding, generator=AnswerModel())[
            "outcome"
        ]
        == "ready"
    )
    trace = client.get(trace_url).json()
    assert len(embedding.calls) == 1
    assert len(trace["attempts"]) == 2 and len(trace["invocations"]) == 3
    assert trace["invocations"][1] == first
    assert trace["turn"]["answer"]["statements"][0]["text"] == "It begins in May."


@pytest.mark.integration
def test_queue_outage_preserves_submission_for_later_delivery(chat_document, monkeypatch):
    from redis.exceptions import ConnectionError
    from rq import Queue

    from folio.conversations.dispatcher import dispatch_once, queue_for

    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"

    def unavailable(*args, **kwargs):
        raise ConnectionError("Redis unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(Queue, "enqueue_call", unavailable)
        response = client.post(
            url, json={"question": "When does it begin?"}, headers={"Idempotency-Key": str(uuid4())}
        )
    assert response.status_code == 202
    turn = response.json()
    assert client.get(url).json()["items"][0]["id"] == turn["id"]
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE conversation_turns SET next_dispatch_at=now() WHERE id=%s", (turn["id"],)
        )
    delivered = dispatch_once(settings, turn_id=turn["id"])
    assert len(delivered) == 1
    queue = queue_for(settings)
    try:
        job = queue.fetch_job(delivered[0]["job_id"])
        assert job.origin == "chat" and job.args == [turn["id"]]
        assert dispatch_once(settings, turn_id=turn["id"]) == []
    finally:
        queue.connection.close()


@pytest.mark.integration
def test_concurrent_tabs_cannot_create_two_first_questions(chat_document):
    from concurrent.futures import ThreadPoolExecutor

    _, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"

    def submit(question):
        return client.post(
            url, json={"question": question}, headers={"Idempotency-Key": str(uuid4())}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, ["When?", "Where?"]))
    assert sorted(r.status_code for r in responses) == [202, 409]
    assert len(client.get(url).json()["items"]) == 1


@pytest.mark.integration
def test_wrong_embedding_space_fails_before_paid_work(chat_document):
    from folio.conversations.processing import process_turn

    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    turn = client.post(
        f"/conversations/{chat['id']}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()

    class WrongSpace(QueryEmbedding):
        def profile(self):
            return super().profile() | {"dimensions": 512}

    embedding, model = WrongSpace(), AnswerModel()
    result = process_turn(turn["id"], settings=settings, embedder=embedding, generator=model)
    assert result == {"outcome": "unavailable", "code": "CHAT_EMBEDDING_SPACE_CHANGED"}
    assert embedding.calls == model.calls == []


@pytest.mark.integration
@pytest.mark.parametrize("change", ["job_timeout", "monitor", "slow_metadata"])
def test_saved_execution_limits_guard_paid_calls(chat_document, monkeypatch, change):
    from folio.conversations import processing

    settings, client, indexes = chat_document
    if change == "job_timeout":
        monkeypatch.setenv("FOLIO_CHAT_TIMEOUT_SECONDS", "250")
    chat = start_chat(client, indexes[0])
    turn = client.post(
        f"/conversations/{chat['id']}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    if change == "job_timeout":
        settings = settings.model_copy(update={"job_timeout_seconds": 600, "lease_seconds": 720})
    if change == "monitor":
        settings = settings.model_copy(update={"worker_monitor_seconds": 200})
    elapsed = [0]
    monkeypatch.setattr(processing, "monotonic", lambda: elapsed[0], raising=False)

    class SlowMetadata(AnswerModel):
        def profile(self):
            if change == "slow_metadata":
                elapsed[0] = 290
            return super().profile()

    embedding, model = QueryEmbedding(), SlowMetadata()
    result = processing.process_turn(
        turn["id"], settings=settings, embedder=embedding, generator=model
    )
    assert result["outcome"] == "unavailable"
    assert result["code"] == (
        "CHAT_EXECUTION_TIME_LIMIT"
        if change == "slow_metadata"
        else "CHAT_EXECUTION_CONFIG_MISMATCH"
    )
    assert not model.calls
    assert len(embedding.calls) == (1 if change == "slow_metadata" else 0)
