import json
import logging
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from test_conversation_followups import Resolver
from test_conversations import AnswerModel, QueryEmbedding, start_chat
from test_conversations import chat_document as chat_document
from test_summaries import Model
from test_summaries import summary_document as summary_document

from folio.conversations.processing import process_turn


class MemoryModel(Model):
    def generate(self, messages, schema, **kwargs):
        self.calls.append(messages)
        source = json.loads(messages[1]["content"])
        return SimpleNamespace(
            content=json.dumps(
                {
                    "notes": [
                        {
                            "text": "The user is tracking the north warehouse delivery date; "
                            "the earlier answer said May.",
                            "turn_ids": [source["history"][0]["turn_id"]],
                        }
                    ]
                }
            ),
            finish_reason="stop",
            prompt_tokens=250,
            completion_tokens=60,
            cost_usd=Decimal("0.0000365"),
            response_id="memory-fixture",
            model="openai/gpt-5-nano",
            provider="openai",
        )


@pytest.fixture
def long_chat(chat_document, monkeypatch):
    settings, client, indexes = chat_document
    for name, value in {
        "MODEL_ID": "openai/gpt-5-nano",
        "REASONING_EFFORT": "minimal",
        "TRIGGER_TOKENS": "750",
        "TARGET_TOKENS": "400",
        "INPUT_LIMIT_TOKENS": "4096",
        "MAX_OUTPUT_TOKENS": "512",
    }.items():
        monkeypatch.setenv(f"FOLIO_MEMORY_{name}", value)
    monkeypatch.setenv("FOLIO_CHAT_HISTORY_LIMIT_TOKENS", "2000")
    monkeypatch.setenv("FOLIO_CHAT_TOKEN_MARGIN", "64")
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_MODEL_ID", "openai/gpt-5-nano")
    monkeypatch.setenv("FOLIO_CHAT_REWRITE_REASONING_EFFORT", "minimal")
    chat = start_chat(client, indexes[0])
    url = f"/conversations/{chat['id']}/turns"
    turns = []
    for sequence in range(3):
        question = (
            "Please track the delivery date for the north warehouse. " * 20
            + f"This is exchange {sequence + 1}."
        )
        response = client.post(
            url,
            json={"question": question, "observed_head": sequence},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 202
        saved = response.json()
        assert process_turn(
            saved["id"],
            settings=settings,
            embedder=QueryEmbedding(),
            generator=AnswerModel(),
            resolver=Resolver(),
        ) == {"outcome": "ready"}
        turns.append(saved)
    return settings, client, chat, url, turns


@pytest.mark.integration
def test_memory_is_durable_and_keeps_originals_and_two_recent_exchanges(long_chat):
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    delivery = dispatch_once(settings)
    assert len(delivery) == 1
    memory_id = delivery[0]["memory_id"]
    assert dispatch_once(settings) == []
    trace = client.get(f"/development/conversation-memories/{memory_id}").json()
    assert trace["memory"]["covered_through"] == 1
    assert 0 < trace["memory"]["policy"]["notes_target_tokens"] <= 200
    assert [turn["turn_id"] for turn in trace["memory"]["input"]["history"]] == [turns[0]["id"]]
    model = MemoryModel()
    assert process_memory(
        memory_id,
        settings=settings,
        generator=model,
        answer_model=Model(),
        resolver=Model(),
        embedder=QueryEmbedding(),
    ) == {"outcome": "ready"}
    assert len(model.calls) == 1
    assert "at most 400 tokens" not in model.calls[0][0]["content"]
    assert client.get(url).json()["items"][0]["question"] == turns[0]["question"]
    next_turn = client.post(
        url,
        json={"question": "What date was that?", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    resolver = Resolver()
    assert process_turn(
        next_turn["id"],
        settings=settings,
        embedder=QueryEmbedding(),
        generator=AnswerModel(),
        resolver=resolver,
    ) == {"outcome": "ready"}
    context = json.loads(resolver.calls[0][1]["content"])
    assert context["memory"]["covered_through"] == 1
    assert [turn["turn_id"] for turn in context["history"]] == [turns[1]["id"], turns[2]["id"]]
    assert len(client.get(url).json()["items"]) == 4


@pytest.mark.integration
def test_oversized_history_waits_without_attempts_and_recovers_lost_delivery(
    long_chat, monkeypatch
):
    from folio.conversations.memory.dispatcher import dispatch_once, queue_for
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    delivery = dispatch_once(settings)[0]
    monkeypatch.setenv("FOLIO_CHAT_HISTORY_LIMIT_TOKENS", "760")
    next_turn = client.post(
        url,
        json={"question": "What date was that?", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    assert process_turn(
        next_turn["id"],
        settings=settings,
        embedder=QueryEmbedding(),
        generator=AnswerModel(),
        resolver=Resolver(),
    ) == {"outcome": "pending"}
    trace = client.get(f"/development/conversation-turns/{next_turn['id']}").json()
    assert trace["turn"]["context_state"] == "preparing"
    assert trace["attempts"] == [] and trace["invocations"] == []
    assert trace["memory_dependency_id"] == delivery["memory_id"]
    memory = client.get(f"/development/conversation-memories/{delivery['memory_id']}").json()
    assert memory["memory"]["foreground"] is True
    queue = queue_for(settings)
    queue.fetch_job(delivery["job_id"]).delete()
    queue.connection.close()
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE conversation_memories SET next_dispatch_at=now() WHERE id=%s",
            (delivery["memory_id"],),
        )
    replacement = dispatch_once(settings)[0]
    assert replacement["memory_id"] == delivery["memory_id"]
    assert replacement["job_id"] != delivery["job_id"]
    assert process_memory(
        delivery["memory_id"],
        settings=settings,
        generator=MemoryModel(),
        answer_model=Model(),
        resolver=Model(),
        embedder=QueryEmbedding(),
    ) == {"outcome": "ready"}
    assert process_turn(
        next_turn["id"],
        settings=settings,
        embedder=QueryEmbedding(),
        generator=AnswerModel(),
        resolver=Resolver(),
    ) == {"outcome": "ready"}
    trace = client.get(f"/development/conversation-turns/{next_turn['id']}").json()
    assert len(trace["attempts"]) == 1
    assert trace["context_snapshot"]["memory"]["covered_through"] == 1


@pytest.mark.integration
def test_memory_publication_does_not_change_a_running_turn_context(long_chat):
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    memory_id = dispatch_once(settings)[0]["memory_id"]

    class PublishingResolver(Resolver):
        def generate(self, messages, schema, **kwargs):
            assert process_memory(
                memory_id,
                settings=settings,
                generator=MemoryModel(),
                answer_model=Model(),
                resolver=Model(),
                embedder=QueryEmbedding(),
            ) == {"outcome": "ready"}
            return super().generate(messages, schema, **kwargs)

    fourth = client.post(
        url,
        json={"question": "What date was that?", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    answer = AnswerModel()
    assert process_turn(
        fourth["id"],
        settings=settings,
        embedder=QueryEmbedding(),
        generator=answer,
        resolver=PublishingResolver(),
    ) == {"outcome": "ready"}
    assert "memory" not in json.loads(answer.calls[0][1]["content"])
    assert len(json.loads(answer.calls[0][1]["content"])["history"]) == 3
    fifth = client.post(
        url,
        json={"question": "Is that date confirmed?", "observed_head": 4},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    trace = client.get(f"/development/conversation-turns/{fifth['id']}").json()
    assert trace["context_snapshot"]["memory"]["id"] == memory_id
    assert [turn["sequence"] for turn in trace["context_snapshot"]["history"]] == [2, 3, 4]


@pytest.mark.integration
@pytest.mark.parametrize("late_ready", [False, True])
def test_waiting_has_a_fixed_deadline_and_does_not_start_an_answer(
    long_chat, monkeypatch, late_ready
):
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    memory_id = dispatch_once(settings)[0]["memory_id"]
    monkeypatch.setenv("FOLIO_CHAT_HISTORY_LIMIT_TOKENS", "760")
    turn = client.post(
        url,
        json={"question": "What date was that?", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    original = client.get(f"/development/conversation-turns/{turn['id']}").json()
    assert process_turn(turn["id"], settings=settings) == {"outcome": "pending"}
    assert (
        client.get(f"/development/conversation-turns/{turn['id']}").json()["context_deadline"]
        == original["context_deadline"]
    )
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE conversation_turns SET context_deadline=now()-interval '1 second' WHERE id=%s",
            (turn["id"],),
        )
    if late_ready:
        assert process_memory(
            memory_id,
            settings=settings,
            generator=MemoryModel(),
            answer_model=Model(),
            resolver=Model(),
            embedder=QueryEmbedding(),
        ) == {"outcome": "ready"}
    assert process_turn(turn["id"], settings=settings) == {
        "outcome": "unavailable",
        "code": "CHAT_CONTEXT_WAIT_EXPIRED",
    }
    trace = client.get(f"/development/conversation-turns/{turn['id']}").json()
    assert trace["attempts"] == [] and trace["invocations"] == []


@pytest.mark.integration
@pytest.mark.parametrize("paused", [False, True])
def test_background_defers_without_a_hold_and_foreground_reuses_it(long_chat, monkeypatch, paused):
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    memory_id = dispatch_once(settings)[0]["memory_id"]
    with psycopg.connect(settings.database_url) as conn:
        conn.execute("UPDATE summary_budget_account SET budget_usd=0.001")
    model = MemoryModel()
    arguments = dict(
        settings=settings,
        generator=model,
        answer_model=Model(),
        resolver=Model(),
        embedder=QueryEmbedding(),
    )
    assert process_memory(memory_id, **arguments) == {"outcome": "deferred"}
    trace = client.get(f"/development/conversation-memories/{memory_id}").json()
    assert trace["attempts"] == [] and model.calls == []
    assert trace["memory"]["deferred_reason"] == "GLOBAL_BUDGET"
    assert dispatch_once(settings) == []
    if paused:
        with psycopg.connect(settings.database_url) as conn:
            conn.execute("UPDATE summary_budget_account SET admission_error='RESERVATION_EXCEEDED'")
    monkeypatch.setenv("FOLIO_CHAT_HISTORY_LIMIT_TOKENS", "760")
    turn = client.post(
        url,
        json={"question": "What date was that?", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    assert (
        client.get(f"/development/conversation-turns/{turn['id']}").json()["memory_dependency_id"]
        == memory_id
    )
    outcome = process_memory(memory_id, **arguments)
    trace = client.get(f"/development/conversation-memories/{memory_id}").json()
    if paused:
        assert outcome == {"outcome": "unavailable", "code": "MEMORY_RESERVATION_EXCEEDED"}
        assert trace["attempts"] == [] and model.calls == []
        assert (
            process_turn(turn["id"], settings=settings)["code"] == "CHAT_CONTEXT_PREPARATION_FAILED"
        )
    else:
        assert outcome == {"outcome": "ready"}
        assert len(trace["attempts"]) == len(model.calls) == 1
        assert Decimal(str(trace["attempts"][0]["cost_usd"])) == Decimal("0.0000365")


@pytest.mark.integration
def test_expired_memory_retries_and_late_bill_cannot_replace_new_result(long_chat):
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    memory_id = dispatch_once(settings)[0]["memory_id"]
    retry_model = MemoryModel()

    class LostWorker(MemoryModel):
        def generate(self, messages, schema, **kwargs):
            result = super().generate(messages, schema, **kwargs)
            with psycopg.connect(settings.database_url) as conn:
                conn.execute(
                    "UPDATE conversation_memories SET lease_expires_at=now()-interval '1 second' "
                    "WHERE id=%s",
                    (memory_id,),
                )
            assert dispatch_once(settings)[0]["memory_id"] == memory_id
            trace = client.get(f"/development/conversation-memories/{memory_id}").json()
            assert trace["attempts"][0]["billing_state"] == "unknown"
            assert Decimal(client.get("/development/settings").json()["runtime"]["held_usd"]) > 0
            assert process_memory(
                memory_id,
                settings=settings,
                generator=retry_model,
                answer_model=Model(),
                resolver=Model(),
                embedder=QueryEmbedding(),
            ) == {"outcome": "ready"}
            result.cost_usd = Decimal("0.0005")
            return result

    old = LostWorker()
    assert process_memory(
        memory_id,
        settings=settings,
        generator=old,
        answer_model=Model(),
        resolver=Model(),
        embedder=QueryEmbedding(),
    ) == {"outcome": "superseded"}
    trace = client.get(f"/development/conversation-memories/{memory_id}").json()
    assert trace["memory"]["state"] == "ready"
    assert len(trace["attempts"]) == 2
    assert [entry["billing_state"] for entry in trace["attempts"]] == ["known", "known"]
    assert Decimal(str(trace["attempts"][0]["cost_usd"])) == Decimal("0.0005")
    assert retry_model.calls == old.calls
    budget = client.get("/development/settings").json()["runtime"]
    assert budget["admission_error"] == "RESERVATION_EXCEEDED"


@pytest.mark.integration
@pytest.mark.parametrize("problem", ["credential", "metadata", "execution"])
def test_memory_preflight_failures_are_bounded_and_never_reserve(long_chat, monkeypatch, problem):
    from folio.ai import OpenRouter, ProviderError
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    memory_id = dispatch_once(settings)[0]["memory_id"]
    model = MemoryModel()
    if problem == "credential":
        monkeypatch.setattr(OpenRouter, "profile", Model.profile)
        model = None
        expected = "MEMORY_PROVIDER_NOT_CONFIGURED"
    elif problem == "metadata":

        class Offline(MemoryModel):
            def profile(self):
                raise ProviderError("SUMMARY_PROVIDER_UNAVAILABLE", retryable=True)

        model = Offline()
        expected = "MEMORY_PROVIDER_UNAVAILABLE"
    else:
        settings = settings.model_copy(update={"worker_monitor_seconds": 100, "lease_seconds": 600})
        expected = "MEMORY_EXECUTION_CONFIG_MISMATCH"
    args = dict(
        settings=settings,
        generator=model,
        answer_model=Model(),
        resolver=Model(),
        embedder=QueryEmbedding(),
    )
    first = process_memory(memory_id, **args)
    if problem == "metadata":
        assert first == {"outcome": "pending", "code": expected}
        final = process_memory(memory_id, **args)
    else:
        final = first
    assert final == {"outcome": "unavailable", "code": expected}
    trace = client.get(f"/development/conversation-memories/{memory_id}").json()
    assert trace["attempts"] == []
    assert trace["memory"]["state"] == "unavailable"
    assert process_memory(memory_id, **args) == {"outcome": "ignored"}


@pytest.mark.integration
@pytest.mark.parametrize("problem", ["current_question", "recent_exchanges"])
def test_context_rejects_what_memory_cannot_shrink_before_paid_work(
    long_chat, monkeypatch, problem
):
    settings, client, chat, url, turns = long_chat
    if problem == "current_question":
        monkeypatch.setenv("FOLIO_CHAT_INPUT_LIMIT_TOKENS", "600")
        question, code = "Which dates? " * 200, "CHAT_INPUT_LIMIT"
    else:
        monkeypatch.setenv("FOLIO_CHAT_HISTORY_LIMIT_TOKENS", "450")
        monkeypatch.setenv("FOLIO_MEMORY_TRIGGER_TOKENS", "400")
        monkeypatch.setenv("FOLIO_MEMORY_TARGET_TOKENS", "200")
        question, code = "What date was that?", "CHAT_HISTORY_LIMIT"
    turn = client.post(
        url,
        json={"question": question, "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    trace = client.get(f"/development/conversation-turns/{turn['id']}").json()
    assert trace["turn"]["state"] == "unavailable"
    assert trace["turn"]["error"]["code"] == code
    assert trace["attempts"] == [] and trace["invocations"] == []
    assert trace["memory_dependency_id"] is None


@pytest.mark.integration
@pytest.mark.parametrize("running", [False, True])
def test_delete_cancels_memory_but_keeps_any_late_charge(long_chat, running):
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    memory_id = dispatch_once(settings)[0]["memory_id"]
    before = Decimal(client.get("/development/settings").json()["runtime"]["spent_usd"])

    class Deleting(MemoryModel):
        def generate(self, messages, schema, **kwargs):
            result = super().generate(messages, schema, **kwargs)
            assert client.delete(f"/conversations/{chat['id']}").status_code == 204
            return result

    if running:
        assert process_memory(
            memory_id,
            settings=settings,
            generator=Deleting(),
            answer_model=Model(),
            resolver=Model(),
            embedder=QueryEmbedding(),
        ) == {"outcome": "superseded"}
    else:
        assert client.delete(f"/conversations/{chat['id']}").status_code == 204
    assert client.get(f"/development/conversation-memories/{memory_id}").status_code == 404
    assert process_memory(memory_id, settings=settings) == {"outcome": "ignored"}
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute(
            "SELECT state,result FROM conversation_memories WHERE id=%s", (memory_id,)
        ).fetchone() == ("unavailable", None)
    after = Decimal(client.get("/development/settings").json()["runtime"]["spent_usd"])
    assert after - before == (Decimal("0.0000365") if running else Decimal(0))


@pytest.mark.integration
@pytest.mark.parametrize("problem", ["malformed", "not_smaller", "wrapper"])
def test_invalid_memory_is_not_published_or_regenerated_for_the_same_prefix(
    long_chat, monkeypatch, problem
):
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    memory_id = dispatch_once(settings)[0]["memory_id"]

    class Invalid(MemoryModel):
        def generate(self, messages, schema, **kwargs):
            result = super().generate(messages, schema, **kwargs)
            if problem == "malformed":
                result.content = "not JSON"
            else:
                result.content = json.dumps(
                    {
                        "notes": [{"text": "date " * 85, "turn_ids": [turns[0]["id"]]}]
                        * (16 if problem == "not_smaller" else 2)
                    }
                )
            return result

    code = "MEMORY_OUTPUT_INVALID" if problem == "malformed" else "MEMORY_OUTPUT_NOT_REDUCED"
    assert process_memory(
        memory_id,
        settings=settings,
        generator=Invalid(),
        answer_model=Model(),
        resolver=Model(),
        embedder=QueryEmbedding(),
    ) == {"outcome": "failed", "code": code}
    trace = client.get(f"/development/conversation-memories/{memory_id}").json()
    assert trace["memory"]["result"] is None and len(trace["attempts"]) == 1
    assert trace["attempts"][0]["billing_state"] == "known"
    monkeypatch.setenv("FOLIO_CHAT_HISTORY_LIMIT_TOKENS", "760")
    turn = client.post(
        url,
        json={"question": "What date was that?", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    saved = client.get(f"{url}/{turn['id']}").json()
    assert (
        saved["state"] == "unavailable"
        and saved["error"]["code"] == "CHAT_CONTEXT_PREPARATION_FAILED"
    )
    assert process_memory(memory_id, settings=settings) == {"outcome": "ignored"}
    assert client.get(url).json()["items"][0]["question"] == turns[0]["question"]


@pytest.mark.integration
def test_compacted_notes_cannot_authorize_an_exact_transcript_reference(long_chat):
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    memory_id = dispatch_once(settings)[0]["memory_id"]
    assert process_memory(
        memory_id,
        settings=settings,
        generator=MemoryModel(),
        answer_model=Model(),
        resolver=Model(),
        embedder=QueryEmbedding(),
    ) == {"outcome": "ready"}
    fourth = client.post(
        url,
        json={"question": "Quote my first question exactly.", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()

    class UnsupportedRecall(Resolver):
        def generate(self, messages, schema, **kwargs):
            result = super().generate(messages, schema, **kwargs)
            result.content = json.dumps(
                {
                    "kind": "transcript_request",
                    "query": None,
                    "response": "A quotation guessed from notes.",
                    "turn_ids": [turns[0]["id"]],
                }
            )
            return result

    embedding, answer = QueryEmbedding(), AnswerModel()
    assert process_turn(
        fourth["id"],
        settings=settings,
        embedder=embedding,
        generator=answer,
        resolver=UnsupportedRecall(),
    ) == {"outcome": "failed", "code": "CHAT_REWRITE_OUTPUT_INVALID"}
    assert embedding.calls == answer.calls == []
    assert client.get(f"{url}/{turns[0]['id']}").json()["question"] == turns[0]["question"]


@pytest.mark.integration
def test_a_waiting_chat_does_not_block_another_ready_dependency(long_chat, monkeypatch):
    from folio.conversations.dispatcher import dispatch_once as dispatch_turns
    from folio.conversations.memory.dispatcher import dispatch_once
    from folio.conversations.memory.processing import process_memory

    settings, client, chat, url, turns = long_chat
    first_memory = dispatch_once(settings)[0]["memory_id"]
    other = start_chat(client, chat["index_id"])
    other_url = f"/conversations/{other['id']}/turns"
    for head in range(3):
        question = client.post(
            other_url,
            json={"question": turns[head]["question"], "observed_head": head},
            headers={"Idempotency-Key": str(uuid4())},
        ).json()
        assert process_turn(
            question["id"],
            settings=settings,
            generator=AnswerModel(),
            resolver=Resolver(),
            embedder=QueryEmbedding(),
        ) == {"outcome": "ready"}
    second_memory = dispatch_once(settings)[0]["memory_id"]
    assert second_memory != first_memory
    monkeypatch.setenv("FOLIO_CHAT_HISTORY_LIMIT_TOKENS", "760")
    waiting = client.post(
        url,
        json={"question": "What date?", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    ready = client.post(
        other_url,
        json={"question": "What date?", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    assert process_memory(
        second_memory,
        settings=settings,
        generator=MemoryModel(),
        answer_model=Model(),
        resolver=Model(),
        embedder=QueryEmbedding(),
    ) == {"outcome": "ready"}
    delivered = dispatch_turns(settings.model_copy(update={"batch_size": 1}))
    assert [item["turn_id"] for item in delivered] == [ready["id"]]
    assert client.get(f"{url}/{waiting['id']}").json()["context_state"] == "preparing"
    assert client.get(f"{other_url}/{ready['id']}").json()["context_state"] is None


@pytest.mark.integration
def test_invalid_tokenizer_does_not_block_preparing_or_dispatching_other_chats(long_chat):
    from folio.conversations.dispatcher import dispatch_once as dispatch_turns
    from folio.conversations.memory.dispatcher import dispatch_once as dispatch_memories

    settings, client, chat, url, turns = long_chat
    bad = client.post(
        url,
        json={"question": "What date?", "observed_head": 3},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    other = start_chat(client, chat["index_id"])
    good = client.post(
        f"/conversations/{other['id']}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE conversation_turns SET context_snapshot=NULL WHERE id IN (%s,%s)",
            (bad["id"], good["id"]),
        )
        conn.execute(
            "UPDATE conversation_turns SET policy=jsonb_set(policy,'{model_id}',%s::jsonb) "
            "WHERE id=%s",
            (json.dumps("unsupported/model"), bad["id"]),
        )
    dispatch_turns(settings)
    failed = client.get(f"/development/conversation-turns/{bad['id']}").json()
    assert failed["turn"]["error"]["code"] == "CHAT_TOKENIZER_UNSUPPORTED"
    assert failed["attempts"] == failed["invocations"] == []
    assert (
        client.get(f"/development/conversation-turns/{good['id']}").json()["context_snapshot"]
        is not None
    )
    dispatch_memories(settings)


@pytest.mark.integration
def test_invalid_memory_tokenizer_is_logged_once_without_blocking_the_dispatcher(long_chat, caplog):
    from folio.conversations.memory.dispatcher import dispatch_once

    settings, client, chat, url, turns = long_chat
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "UPDATE conversation_turns SET policy=jsonb_set(policy,'{memory,model_id}',%s::jsonb) "
            "WHERE id=%s",
            (json.dumps("unsupported/model"), turns[-1]["id"]),
        )
    logger = logging.getLogger("folio.observability")
    propagate = logger.propagate
    logger.propagate = False
    logger.addHandler(caplog.handler)
    try:
        assert dispatch_once(settings) == []
        assert dispatch_once(settings) == []
    finally:
        logger.removeHandler(caplog.handler)
        logger.propagate = propagate
    events = [
        record for record in caplog.records if "chat_memory_planning_unavailable" in record.message
    ]
    assert len(events) == 1
    assert "SUMMARY_TOKENIZER_UNSUPPORTED" in events[0].message
