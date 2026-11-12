import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from test_conversations import AnswerModel, QueryEmbedding, start_chat
from test_conversations import chat_document as chat_document
from test_summaries import Model
from test_summaries import summary_document as summary_document

from folio.conversations.processing import process_turn


class Resolver(Model):
    def generate(self, messages, schema, **kwargs):
        self.calls.append(messages)
        return SimpleNamespace(
            content=json.dumps(
                {
                    "kind": "document_query",
                    "query": "Does the project begin in May?",
                    "response": None,
                    "turn_ids": [],
                }
            ),
            finish_reason="stop",
            prompt_tokens=150,
            completion_tokens=35,
            cost_usd=Decimal("0.0000215"),
            response_id="resolver-fixture",
            model="openai/gpt-5-nano",
            provider="openai",
        )


@pytest.fixture
def completed_chat(chat_document, monkeypatch):
    settings, client, indexes = chat_document
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_MODEL_ID", "openai/gpt-5-nano")
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_REASONING_EFFORT", "minimal")
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    first = client.post(
        url, json={"question": "When does it begin?"}, headers={"Idempotency-Key": str(uuid4())}
    ).json()
    assert process_turn(
        first["id"], settings=settings, embedder=QueryEmbedding(), generator=AnswerModel()
    ) == {"outcome": "ready"}
    return settings, client, url, first


@pytest.mark.integration
def test_followup_resolves_subject_and_retrieves_fresh_scoped_evidence(chat_document, monkeypatch):
    settings, client, indexes = chat_document
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_MODEL_ID", "openai/gpt-5-nano")
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_REASONING_EFFORT", "minimal")
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    first = client.post(
        url,
        json={"question": "When does the project begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    assert process_turn(
        first["id"], settings=settings, embedder=QueryEmbedding(), generator=AnswerModel()
    ) == {"outcome": "ready"}
    submitted = client.post(
        url,
        json={"question": "Is that in May?", "observed_head": 1},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert submitted.status_code == 202
    second = submitted.json()
    assert second["sequence"] == 2 and second["parent_sequence"] == 1
    resolver, embedding, answer = Resolver(), QueryEmbedding(), AnswerModel()
    assert process_turn(
        second["id"], settings=settings, embedder=embedding, generator=answer, resolver=resolver
    ) == {"outcome": "ready"}
    context = json.loads(resolver.calls[0][1]["content"])["history"]
    assert context == [
        {
            "turn_id": first["id"],
            "sequence": 1,
            "question": "When does the project begin?",
            "outcome": "answer",
            "answer": ["It begins in May."],
        }
    ]
    assert embedding.calls == [["Does the project begin in May?"]]
    prompt = json.loads(answer.calls[0][1]["content"])
    assert prompt["question"] == "Is that in May?"
    assert prompt["resolved_question"] == "Does the project begin in May?"
    assert prompt["history"] == context
    assert "OTHER_DOCUMENT_SENTINEL" not in json.dumps(prompt)
    saved = client.get(f"{url}/{second['id']}").json()
    assert saved["question"] == "Is that in May?"
    assert saved["resolved_question"] == "Does the project begin in May?"
    assert saved["citations"][0]["text"] == "The project begins in May."
    history = client.get(url).json()
    assert [turn["sequence"] for turn in history["items"]] == [1, 2]
    assert client.get(f"/conversations/{chat['id']}").json()["head_sequence"] == 2


@pytest.mark.integration
def test_replay_precedes_head_checks_and_only_one_concurrent_followup_is_accepted(chat_document):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    key = {"Idempotency-Key": str(uuid4())}
    original = {"question": "When does it begin?", "observed_head": 0}
    first = client.post(url, json=original, headers=key).json()
    process_turn(first["id"], settings=settings, embedder=QueryEmbedding(), generator=AnswerModel())

    def submit(question):
        return client.post(
            url,
            json={"question": question, "observed_head": 1},
            headers={"Idempotency-Key": str(uuid4())},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, ["Is that in May?", "What about June?"]))
    assert sorted(response.status_code for response in results) == [202, 409]
    assert client.post(url, json=original, headers=key).json()["id"] == first["id"]
    assert client.post(url, json=original | {"observed_head": 1}, headers=key).status_code == 409
    assert (
        client.post(
            url,
            json={"question": "Too soon", "observed_head": 2},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 409
    )
    assert [turn["sequence"] for turn in client.get(url).json()["items"]] == [1, 2]


@pytest.mark.integration
def test_history_opens_latest_page_and_pages_back_without_changing_order(chat_document):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    first = client.post(
        url, json={"question": "When does it begin?"}, headers={"Idempotency-Key": str(uuid4())}
    ).json()
    process_turn(first["id"], settings=settings, embedder=QueryEmbedding(), generator=AnswerModel())
    client.post(
        url,
        json={"question": "What about June?", "observed_head": 1},
        headers={"Idempotency-Key": str(uuid4())},
    )
    latest = client.get(f"{url}?limit=1").json()
    assert [turn["sequence"] for turn in latest["items"]] == [2]
    assert latest["next_before"] == 2 and latest["next_after"] is None
    older = client.get(f"{url}?before_sequence=2&limit=1").json()
    assert [turn["sequence"] for turn in older["items"]] == [1]
    assert older["next_before"] is None
    assert client.get(f"{url}?after=0&limit=1").json()["next_after"] == 1
    assert client.get(f"{url}?after=0&before_sequence=2").status_code == 400


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["clarification", "transcript_request"])
def test_non_document_followup_uses_original_turns_without_pdf_calls(
    chat_document, monkeypatch, kind
):
    settings, client, indexes = chat_document
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_MODEL_ID", "openai/gpt-5-nano")
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_REASONING_EFFORT", "minimal")
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    first = client.post(
        url, json={"question": "When does it begin?"}, headers={"Idempotency-Key": str(uuid4())}
    ).json()
    process_turn(first["id"], settings=settings, embedder=QueryEmbedding(), generator=AnswerModel())
    second = client.post(
        url,
        json={"question": "What did I ask first?", "observed_head": 1},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    response = {
        "kind": kind,
        "query": None,
        "response": "You asked: When does it begin?"
        if kind == "transcript_request"
        else "Which project do you mean?",
        "turn_ids": [first["id"]] if kind == "transcript_request" else [],
    }

    class DirectResponse(Resolver):
        def generate(self, messages, schema, **kwargs):
            result = super().generate(messages, schema, **kwargs)
            result.content = json.dumps(response)
            return result

    embedding, answer = QueryEmbedding(), AnswerModel()
    assert process_turn(
        second["id"],
        settings=settings,
        embedder=embedding,
        generator=answer,
        resolver=DirectResponse(),
    ) == {"outcome": "ready"}
    assert not embedding.calls and not answer.calls
    saved = client.get(f"{url}/{second['id']}").json()
    assert saved["answer"]["outcome"] == ("transcript" if kind == "transcript_request" else kind)
    assert saved["citations"] == [] and saved["resolved_question"] is None
    trace = client.get(f"/development/conversation-turns/{second['id']}").json()
    assert trace["resolution"] == response
    assert trace["context_snapshot"]["through_sequence"] == 1
    assert trace["context_snapshot"]["history"][0]["turn_id"] == first["id"]
    assert len(trace["context_snapshot"]["sha256"]) == 64
    assert [call["stage"] for call in trace["invocations"]] == ["rewrite"]


@pytest.mark.integration
def test_history_limit_fails_explicitly_before_any_new_paid_stage(completed_chat, monkeypatch):
    settings, client, url, _ = completed_chat
    monkeypatch.setenv("FOLIO_CHAT_HISTORY_LIMIT_TOKENS", "1")
    second = client.post(
        url,
        json={"question": "Is that in May?", "observed_head": 1},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    resolver, embedding, answer = Resolver(), QueryEmbedding(), AnswerModel()
    assert process_turn(
        second["id"], settings=settings, resolver=resolver, embedder=embedding, generator=answer
    ) == {"outcome": "unavailable", "code": "CHAT_HISTORY_LIMIT"}
    assert not resolver.calls and not embedding.calls and not answer.calls
    saved = client.get(f"{url}/{second['id']}").json()
    assert "history" in saved["error"]["message"].lower()
    assert saved["question"] == "Is that in May?" and saved["answer"] is None
    assert client.get(f"/development/conversation-turns/{second['id']}").json()["invocations"] == []


@pytest.mark.integration
def test_retry_reuses_resolution_context_and_vector_without_repaying(completed_chat):
    settings, client, url, _ = completed_chat
    second = client.post(
        url,
        json={"question": "Is that in May?", "observed_head": 1},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()

    class InterruptedAnswer(AnswerModel):
        def generate(self, *args, **kwargs):
            super().generate(*args, **kwargs)
            raise TimeoutError("Controlled unknown answer outcome")

    resolver, embedding = Resolver(), QueryEmbedding()
    assert (
        process_turn(
            second["id"],
            settings=settings,
            resolver=resolver,
            embedder=embedding,
            generator=InterruptedAnswer(),
        )["outcome"]
        == "pending"
    )
    trace_url = f"/development/conversation-turns/{second['id']}"
    interrupted = client.get(trace_url).json()
    answer = AnswerModel()
    assert process_turn(
        second["id"], settings=settings, resolver=resolver, embedder=embedding, generator=answer
    ) == {"outcome": "ready"}
    saved = client.get(trace_url).json()
    assert len(resolver.calls) == len(embedding.calls) == 1
    assert saved["context_snapshot"] == interrupted["context_snapshot"]
    assert saved["resolution"] == interrupted["resolution"]
    assert saved["invocations"][:3] == interrupted["invocations"]
    assert [call["stage"] for call in saved["invocations"]] == [
        "rewrite",
        "embedding",
        "answer",
        "answer",
    ]
    assert saved["invocations"][2]["billing_state"] == "unknown"
    assert Decimal(saved["invocations"][2]["reserved_usd"]) > 0
    assert (
        json.loads(answer.calls[0][1]["content"])["history"] == saved["context_snapshot"]["history"]
    )


@pytest.mark.integration
def test_saved_rewrite_prompt_survives_retry_after_new_prompt_default(completed_chat):
    settings, client, url, _ = completed_chat
    second = client.post(
        url,
        json={"question": "Is that in May?", "observed_head": 1},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE conversation_turns SET policy=policy-'rewrite_prompt_version' WHERE id=%s",
            (second["id"],),
        )

    class InterruptedResolver(Resolver):
        def generate(self, *args, **kwargs):
            super().generate(*args, **kwargs)
            raise TimeoutError("Controlled unknown rewrite outcome")

    interrupted = InterruptedResolver()
    assert process_turn(second["id"], settings=settings, resolver=interrupted)["outcome"] == (
        "pending"
    )
    # The deployed original instructions are part of this saved policy's retry contract.
    assert hashlib.sha256(interrupted.calls[0][0]["content"].encode()).hexdigest() == (
        "ef962d6e6179f7f74a1ced14e759e8410f0da430051a4dd26d3fea938285ba41"
    )
    legacy = Resolver()
    assert process_turn(
        second["id"],
        settings=settings,
        resolver=legacy,
        embedder=QueryEmbedding(),
        generator=AnswerModel(),
    ) == {"outcome": "ready"}
    assert legacy.calls == interrupted.calls
    saved = client.get(f"/development/conversation-turns/{second['id']}").json()
    assert "rewrite_prompt_version" not in saved["policy"]
    assert saved["invocations"][0]["billing_state"] == "unknown"

    third = client.post(
        url,
        json={"question": "What is the project number?", "observed_head": 2},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    policy = client.get(f"/development/conversation-turns/{third['id']}").json()["policy"]
    assert policy["rewrite_prompt_version"] == 2
    assert policy["prompt_version"] == policy["schema_version"] == 3
    current = Resolver()
    assert process_turn(
        third["id"],
        settings=settings,
        resolver=current,
        embedder=QueryEmbedding(),
        generator=AnswerModel(),
    ) == {"outcome": "ready"}
    assert current.calls[0][0] != legacy.calls[0][0]


@pytest.mark.integration
@pytest.mark.parametrize("failure", ["unknown_reference", "truncated", "empty_query"])
def test_invalid_resolution_retains_bill_but_never_starts_pdf_calls(completed_chat, failure):
    settings, client, url, _ = completed_chat
    second = client.post(
        url,
        json={"question": "What did I ask?", "observed_head": 1},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()

    class InvalidResolver(Resolver):
        def generate(self, *args, **kwargs):
            result = super().generate(*args, **kwargs)
            if failure == "truncated":
                result.finish_reason = "length"
            elif failure == "unknown_reference":
                result.content = json.dumps(
                    {
                        "kind": "transcript_request",
                        "query": None,
                        "response": "An invented prior question.",
                        "turn_ids": [second["id"]],
                    }
                )
            else:
                result.content = json.dumps(
                    {"kind": "document_query", "query": "  ", "response": None, "turn_ids": []}
                )
            return result

    embedding, answer = QueryEmbedding(), AnswerModel()
    outcome = process_turn(
        second["id"],
        settings=settings,
        resolver=InvalidResolver(),
        embedder=embedding,
        generator=answer,
    )
    assert outcome["outcome"] == "failed"
    assert outcome["code"] == (
        "CHAT_REWRITE_OUTPUT_INCOMPLETE"
        if failure == "truncated"
        else "CHAT_REWRITE_OUTPUT_INVALID"
    )
    assert not embedding.calls and not answer.calls
    trace = client.get(f"/development/conversation-turns/{second['id']}").json()
    assert trace["resolution"] is None and trace["turn"]["answer"] is None
    assert Decimal(str(trace["invocations"][0]["cost_usd"])) == Decimal("0.0000215")


@pytest.mark.integration
def test_deleted_rewrite_can_settle_but_cannot_publish_or_start_embedding(completed_chat):
    settings, client, url, _ = completed_chat
    second = client.post(
        url,
        json={"question": "Is that in May?", "observed_head": 1},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()

    class DeletedResolver(Resolver):
        def generate(self, *args, **kwargs):
            assert client.delete(url.removesuffix("/turns")).status_code == 204
            return super().generate(*args, **kwargs)

    embedding, answer = QueryEmbedding(), AnswerModel()
    assert process_turn(
        second["id"],
        settings=settings,
        resolver=DeletedResolver(),
        embedder=embedding,
        generator=answer,
    ) == {"outcome": "superseded"}
    assert not embedding.calls and not answer.calls
    assert client.get(f"{url}/{second['id']}").status_code == 404
    runtime = client.get("/development/settings").json()["runtime"]
    assert Decimal(runtime["spent_usd"]) == Decimal("0.0000636")
    assert Decimal(runtime["held_usd"]) == 0
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute(
            "SELECT resolution,result FROM conversation_turns WHERE id=%s", (second["id"],)
        ).fetchone() == (None, None)


@pytest.mark.integration
def test_evidence_fits_as_whole_ranked_chunks_and_saved_selection_survives_retry(
    chat_document, monkeypatch
):
    settings, client, indexes = chat_document
    monkeypatch.setenv("FOLIO_CHAT_INPUT_LIMIT_TOKENS", "3000")
    long_chunks = ["Tax is excluded. " * 100, "A fee applies. " * 100]
    with psycopg.connect(settings.database_url) as conn:
        revision = conn.execute(
            "SELECT revision_id FROM document_indexes WHERE id=%s", (indexes[0],)
        ).fetchone()[0]
        for ordinal, text in enumerate(long_chunks, start=2):
            conn.execute(
                "INSERT INTO index_chunks(index_id,revision_id,ordinal,batch_no,"
                "text,tokens,sha256,embedding) "
                "VALUES (%s,%s,%s,1,%s,400,%s,%s::vector)",
                (
                    indexes[0],
                    revision,
                    ordinal,
                    text,
                    str(ordinal) * 64,
                    json.dumps([1.0] + [0.0] * 1535),
                ),
            )
            conn.execute(
                "INSERT INTO chunk_sources VALUES (%s,%s,%s,0,'last','body')",
                (indexes[0], revision, ordinal),
            )
        conn.execute("UPDATE document_indexes SET chunk_count=3 WHERE id=%s", (indexes[0],))
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    first = client.post(
        url, json={"question": "When does it begin?"}, headers={"Idempotency-Key": str(uuid4())}
    ).json()

    class InterruptedAnswer(AnswerModel):
        def generate(self, *args, **kwargs):
            super().generate(*args, **kwargs)
            raise TimeoutError("Controlled answer interruption")

    interrupted = InterruptedAnswer()
    embedding = QueryEmbedding()
    assert (
        process_turn(first["id"], settings=settings, embedder=embedding, generator=interrupted)[
            "outcome"
        ]
        == "pending"
    )
    supplied = json.loads(interrupted.calls[0][1]["content"])["evidence"]
    texts = [passage["text"] for passage in supplied]
    assert 0 < len(supplied) < 3
    assert texts == ["The project begins in May.", *long_chunks][: len(supplied)]
    before = client.get(f"/development/conversation-turns/{first['id']}").json()
    assert len(before["evidence"]) == len(supplied)
    assert before["input_manifest"]["evidence_candidates"] == 3
    answer = AnswerModel()
    assert process_turn(first["id"], settings=settings, embedder=embedding, generator=answer) == {
        "outcome": "ready"
    }
    assert answer.calls == interrupted.calls
    assert len(embedding.calls) == 1


@pytest.mark.integration
@pytest.mark.parametrize("version", [1, 2])
def test_saved_legacy_retry_keeps_original_prompt_without_context_or_resolver(
    chat_document, version
):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    turn = client.post(
        f"/conversations/{chat['id']}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE conversation_turns SET policy=policy || %s::jsonb WHERE id=%s",
            (
                json.dumps(
                    {"prompt_version": version, "schema_version": version, "retrieval_version": 1}
                ),
                turn["id"],
            ),
        )

    class Interrupted(AnswerModel):
        def generate(self, messages, schema, **kwargs):
            payload = json.loads(messages[1]["content"])
            assert "history" not in payload and "resolved_question" not in payload
            assert ("title" in schema["properties"]) is (version == 2)
            super().generate(messages, schema, **kwargs)
            raise TimeoutError("Controlled legacy interruption")

    resolver, embedding, interrupted = Resolver(), QueryEmbedding(), Interrupted()
    assert (
        process_turn(
            turn["id"],
            settings=settings,
            resolver=resolver,
            embedder=embedding,
            generator=interrupted,
        )["outcome"]
        == "pending"
    )
    answer = AnswerModel()
    assert process_turn(
        turn["id"], settings=settings, resolver=resolver, embedder=embedding, generator=answer
    ) == {"outcome": "ready"}
    assert answer.calls == interrupted.calls
    assert not resolver.calls and len(embedding.calls) == 1
    trace = client.get(f"/development/conversation-turns/{turn['id']}").json()
    assert trace["context_snapshot"] is None and trace["resolution"] is None


@pytest.mark.integration
def test_failed_question_remains_unanswered_context_without_technical_error(
    chat_document, monkeypatch
):
    settings, client, indexes = chat_document
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_MODEL_ID", "openai/gpt-5-nano")
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_REASONING_EFFORT", "minimal")
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    first = client.post(
        url, json={"question": "When does it begin?"}, headers={"Idempotency-Key": str(uuid4())}
    ).json()

    class InvalidAnswer(AnswerModel):
        def generate(self, *args, **kwargs):
            result = super().generate(*args, **kwargs)
            result.content = result.content.replace('"S1"', '"not_supplied"')
            return result

    assert (
        process_turn(
            first["id"], settings=settings, embedder=QueryEmbedding(), generator=InvalidAnswer()
        )["outcome"]
        == "failed"
    )
    second = client.post(
        url,
        json={"question": "Is that in May?", "observed_head": 1},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    resolver = Resolver()
    assert process_turn(
        second["id"],
        settings=settings,
        resolver=resolver,
        embedder=QueryEmbedding(),
        generator=AnswerModel(),
    ) == {"outcome": "ready"}
    history = json.loads(resolver.calls[0][1]["content"])["history"]
    assert history == [
        {
            "turn_id": first["id"],
            "sequence": 1,
            "question": "When does it begin?",
            "outcome": "unanswered",
            "answer": [],
        }
    ]
    assert client.get(url).json()["items"][0]["state"] == "failed"
