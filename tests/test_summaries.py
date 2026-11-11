import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from folio.ai import OpenRouter
from folio.api import create_app
from folio.config import Settings
from folio.ingestion.parsing.evidence import Element, Extraction, Location, Page
from folio.ingestion.processing import process_attempt


def available_evidence(path, config):
    return Extraction(
        [Page(1, 612, 792, "content_recovered")],
        [
            Element(
                "first",
                "paragraph",
                0,
                None,
                "The project begins in May.",
                None,
                None,
                [Location(1)],
            ),
            Element(
                "last", "paragraph", 1, None, "The budget excludes tax.", None, None, [Location(1)]
            ),
        ],
        [],
        "success",
        {"fixture": True},
        {"text": "Synthetic summary fixture"},
        0.1,
    )


class Model:
    def __init__(self):
        self.calls = []
        self.content = {
            "overview": {
                "text": "A project starts in May with a tax-exclusive budget.",
                "source_ids": ["first", "last"],
            },
            "points": [
                {"text": "The project begins in May.", "source_ids": ["first"]},
                {"text": "A budget is described.", "source_ids": ["last"]},
                {"text": "Tax is excluded.", "source_ids": ["last"]},
            ],
        }

    def profile(self):
        return {
            "model_id": "openai/gpt-5-nano",
            "provider": "openai",
            "tokenizer": "o200k_base",
            "context_tokens": 400000,
            "max_prompt_tokens": 272000,
            "max_completion_tokens": 128000,
            "input_price_per_million": "0.05",
            "output_price_per_million": "0.40",
        }

    def generate(self, messages, schema):
        self.calls.append(messages)
        return SimpleNamespace(
            content=json.dumps(self.content),
            finish_reason="stop",
            prompt_tokens=100,
            completion_tokens=100,
            cost_usd=Decimal("0.000045"),
            response_id="fixture-response",
            model="openai/gpt-5-nano",
            provider="openai",
        )


@pytest.fixture
def summary_document(tmp_path, monkeypatch):
    # The fake model and budget expectations must not inherit the application's live policy.
    for name, value in {
        "ENABLED": "true",
        "MODEL_ID": "openai/gpt-5-nano",
        "PROVIDER": "openai",
        "INPUT_LIMIT_TOKENS": "64000",
        "MAX_OUTPUT_TOKENS": "4096",
        "TOKEN_MARGIN": "2048",
        "REASONING_EFFORT": "minimal",
        "TIMEOUT_SECONDS": "90",
        "MAX_ATTEMPTS": "2",
        "BUDGET_USD": "1",
        "DOCUMENT_BUDGET_USD": "0.10",
    }.items():
        monkeypatch.setenv(f"FOLIO_SUMMARY_{name}", value)
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    settings = Settings(
        _env_file=None,
        artifact_root=tmp_path,
        development_mode=True,
        parser_timeout_seconds=240,
        job_timeout_seconds=300,
        worker_monitor_seconds=10,
        lease_seconds=420,
        retry_delays_seconds=(0,),
        retry_jitter_seconds=0,
    )
    with psycopg.connect(settings.database_url) as connection:
        connection.execute("DELETE FROM summary_budget_account")
    with TestClient(create_app(settings), base_url="http://localhost") as client:

        def publish(parser=available_evidence):
            receipt = client.post(
                "/documents",
                headers={"Idempotency-Key": str(uuid4())},
                files={"file": ("summary.pdf", b"%PDF-1.4\nSynthetic summary input")},
            ).json()
            status = client.get(receipt["status_url"]).json()
            result = process_attempt(
                receipt["request_id"],
                status["authorized_attempt_id"],
                settings=settings,
                parser=parser,
            )
            return receipt, result.get("revision_id")

        yield settings, client, publish


@pytest.mark.integration
def test_automatic_summary_is_saved_and_reused_without_another_call(summary_document):
    settings, client, publish = summary_document
    _, revision_id = publish()
    url = f"/revisions/{revision_id}/summary"
    pending = client.get(url)
    assert pending.status_code == 200
    assert pending.json()["state"] == "pending"

    from folio.summaries.processing import process_summary

    model = Model()
    run_id = pending.json()["run_id"]
    assert process_summary(run_id, settings=settings, client=model)["outcome"] == "ready"
    saved = client.get(url).json()
    assert saved["state"] == "ready"
    assert saved["overview"] == model.content["overview"]
    assert len(saved["points"]) == 3
    assert {citation["source_id"]: citation["pages"] for citation in saved["citations"]} == {
        "first": [1],
        "last": [1],
    }
    assert process_summary(run_id, settings=settings, client=model)["outcome"] == "ignored"
    assert client.get(url).json() == saved
    assert len(model.calls) == 1


@pytest.mark.integration
def test_deepseek_summary_flows_from_prepared_evidence_to_saved_citations(
    summary_document, monkeypatch
):
    from folio.summaries.config import SummarySettings
    from folio.summaries.processing import process_summary

    settings, client, publish = summary_document
    for name, value in {
        "MODEL_ID": "deepseek/deepseek-v4.1-flash-1017",
        "PROVIDER": "fireworks",
        "MAX_OUTPUT_TOKENS": "16384",
        "REASONING_EFFORT": "none",
        "DOCUMENT_BUDGET_USD": "0.40",
    }.items():
        monkeypatch.setenv(f"FOLIO_SUMMARY_{name}", value)
    policy = SummarySettings().policy(settings)
    content = Model().content
    calls = []

    def respond(request):
        if request.url.path == "/api/v1/models":
            data = [{"id": policy["model_id"], "reasoning": {"supported_efforts": ["none"]}}]
        elif request.method == "GET":
            data = {
                "id": policy["model_id"],
                "endpoints": [
                    {
                        "tag": "fireworks",
                        "provider_name": "Fireworks",
                        "status": 0,
                        "context_length": 1048576,
                        "max_prompt_tokens": None,
                        "max_completion_tokens": 943718,
                        "pricing": {"prompt": "0.0000003", "completion": "0.0000012"},
                        "supported_parameters": [
                            "max_tokens",
                            "response_format",
                            "structured_outputs",
                            "reasoning",
                        ],
                    }
                ],
            }
        else:
            calls.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "model": policy["model_id"],
                    "provider": "Fireworks",
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": json.dumps(content)}}
                    ],
                    "usage": {"prompt_tokens": 600, "completion_tokens": 200, "cost": 0.00042},
                },
            )
        return httpx.Response(200, json={"data": data})

    _, revision_id = publish()
    url = f"/revisions/{revision_id}/summary"
    run_id = client.get(url).json()["run_id"]
    model = OpenRouter(policy, "test-key", transport=httpx.MockTransport(respond))
    assert process_summary(run_id, settings=settings, client=model)["outcome"] == "ready"
    saved = client.get(url).json()
    assert saved["overview"] == content["overview"]
    assert saved["points"] == content["points"]
    assert {citation["source_id"]: citation["pages"] for citation in saved["citations"]} == {
        "first": [1],
        "last": [1],
    }
    assert Decimal(saved["usage"]["cost_usd"]) == Decimal("0.00042")
    assert saved["usage"]["last_finish_reason"] == "stop"
    assert process_summary(run_id, settings=settings, client=model)["outcome"] == "ignored"
    assert len(calls) == 1
    assert "The budget excludes tax." in calls[0]["messages"][1]["content"]
    assert calls[0]["max_tokens"] == 16384


@pytest.mark.integration
def test_tiny_document_can_publish_one_meaningful_cited_point(summary_document):
    from folio.summaries.processing import process_summary

    settings, client, publish = summary_document

    def tiny_document(path, config):
        extraction = available_evidence(path, config)
        return replace(extraction, elements=extraction.elements[:1])

    _, revision_id = publish(tiny_document)
    url = f"/revisions/{revision_id}/summary"
    model = Model()
    statement = {"text": "The project begins in May.", "source_ids": ["first"]}
    model.content = {"overview": statement, "points": [statement]}
    process_summary(client.get(url).json()["run_id"], settings=settings, client=model)

    saved = client.get(url).json()
    assert saved["state"] == "ready"
    assert saved["points"] == [statement]
    assert {citation["source_id"]: citation["pages"] for citation in saved["citations"]} == {
        "first": [1]
    }


@pytest.mark.integration
@pytest.mark.parametrize(
    "defect",
    [
        "foreign_source",
        "invalid_json",
        "no_points",
        "too_many_points",
        "too_many_sources",
        "long_overview",
        "long_point",
    ],
)
def test_invalid_output_retries_once_without_publishing_or_losing_evidence(
    summary_document, defect
):
    from folio.summaries.processing import process_summary

    settings, client, publish = summary_document
    receipt, revision_id = publish()
    url = f"/revisions/{revision_id}/summary"
    run_id = client.get(url).json()["run_id"]

    class Invalid(Model):
        def generate(self, messages, schema):
            result = super().generate(messages, schema)
            if defect == "foreign_source":
                bad = json.loads(result.content)
                bad["points"][0]["source_ids"] = ["another-document-source"]
                result.content = json.dumps(bad)
            elif defect in ("long_overview", "long_point"):
                bad = json.loads(result.content)
                statement = bad["overview"] if defect == "long_overview" else bad["points"][0]
                statement["text"] = "x" * (601 if defect == "long_overview" else 401)
                result.content = json.dumps(bad)
            elif defect in ("no_points", "too_many_points"):
                bad = json.loads(result.content)
                bad["points"] = [] if defect == "no_points" else bad["points"] * 2
                result.content = json.dumps(bad)
            elif defect == "too_many_sources":
                bad = json.loads(result.content)
                # Existing IDs isolate the response-size contract from citation support.
                bad["points"][0]["source_ids"] = ["first"] * 9
                result.content = json.dumps(bad)
            else:
                result.content = "{incomplete"
            return result

    model = Invalid()
    process_summary(run_id, settings=settings, client=model)
    retrying = client.get(url).json()
    assert retrying["state"] == "pending"
    assert retrying["overview"] is None
    process_summary(run_id, settings=settings, client=model)
    final = client.get(url).json()
    assert final["state"] == "failed"
    assert final["error"]["code"] == "INVALID_OUTPUT"
    assert final["usage"]["attempts"] == 2
    assert Decimal(final["usage"]["cost_usd"]) == Decimal("0.00009")
    assert process_summary(run_id, settings=settings, client=model)["outcome"] == "ignored"
    assert len(model.calls) == 2
    assert client.get(receipt["status_url"]).json()["state"] == "succeeded"
    assert client.get(f"/revisions/{revision_id}/evidence").status_code == 200


@pytest.mark.integration
def test_output_limit_is_terminal_and_preserves_usage_and_evidence(summary_document):
    from folio.summaries.processing import process_summary

    settings, client, publish = summary_document
    receipt, revision_id = publish()
    url = f"/revisions/{revision_id}/summary"
    run_id = client.get(url).json()["run_id"]

    class Truncated(Model):
        def generate(self, messages, schema):
            result = super().generate(messages, schema)
            result.content = '{"overview":'
            result.finish_reason = "length"
            result.completion_tokens = 4096
            result.reasoning_tokens = 50
            return result

    model = Truncated()
    process_summary(run_id, settings=settings, client=model)
    saved = client.get(url).json()
    assert saved["state"] == "failed"
    assert saved["error"]["code"] == "SUMMARY_OUTPUT_LIMIT"
    assert saved["overview"] is None
    assert saved["usage"]["attempts"] == 1
    assert saved["usage"]["last_finish_reason"] == "length"
    assert saved["usage"]["reasoning_tokens"] == 50
    assert saved["usage"]["response_characters"] == 12
    assert saved["usage"]["completion_tokens"] == 4096
    assert Decimal(saved["usage"]["cost_usd"]) == Decimal("0.000045")
    assert process_summary(run_id, settings=settings, client=model)["outcome"] == "ignored"
    assert len(model.calls) == 1
    assert client.get(receipt["status_url"]).json()["state"] == "succeeded"
    assert client.get(f"/revisions/{revision_id}/evidence").status_code == 200


@pytest.mark.integration
def test_complete_input_preserves_tables_and_rejects_an_oversized_document(
    summary_document, monkeypatch
):
    from folio.summaries.processing import process_summary

    settings, client, publish = summary_document
    monkeypatch.setenv("FOLIO_SUMMARY_INPUT_LIMIT_TOKENS", "8192")
    table = {
        "row_count": 2,
        "column_count": 2,
        "cells": [
            {
                "row": 0,
                "column": 0,
                "row_span": 1,
                "column_span": 2,
                "text": "Net cost, excluding tax",
                "column_header": True,
                "row_header": False,
            },
            {
                "row": 1,
                "column": 0,
                "row_span": 1,
                "column_span": 1,
                "text": "Phase A",
                "column_header": False,
                "row_header": True,
            },
            {
                "row": 1,
                "column": 1,
                "row_span": 1,
                "column_span": 1,
                "text": "120",
                "column_header": False,
                "row_header": False,
            },
        ],
    }
    clauses = [
        f"Retention rule {number}: keep the register for {number} years." for number in range(1, 65)
    ]

    def with_table(path, config):
        extraction = available_evidence(path, config)
        extraction.elements.append(
            Element(
                "costs",
                "table",
                2,
                None,
                None,
                table,
                None,
                [Location(1, 50, 100, 500, 200), Location(1), Location(2)],
            )
        )
        extraction.elements.append(
            Element(
                "cost-caption",
                "caption",
                3,
                "costs",
                "Figures exclude sales tax.",
                None,
                None,
                [Location(1)],
            )
        )
        extraction.elements.extend(
            Element(
                f"clause-{number}",
                "paragraph",
                number + 3,
                None,
                text,
                None,
                None,
                [Location(2, 20.25, 40.75, 130.5, 60.25, 0, len(text))],
            )
            for number, text in enumerate(clauses, 1)
        )
        extraction.pages.append(Page(2, 612, 792, "content_recovered"))
        extraction.pages.append(
            Page(3, 612, 792, "no_content_recovered", [{"code": "NO_CONTENT", "page_no": 3}])
        )
        return extraction

    _, revision_id = publish(with_table)
    summary = client.get(f"/revisions/{revision_id}/summary").json()
    model = Model()
    assert process_summary(summary["run_id"], settings=settings, client=model)["outcome"] == "ready"
    sent = json.loads(model.calls[0][1]["content"])
    assert [element["element_id"] for element in sent["evidence"]] == [
        "first",
        "last",
        "costs",
        "cost-caption",
        *[f"clause-{number}" for number in range(1, 65)],
    ]
    assert [element["text"] for element in sent["evidence"] if "text" in element] == [
        "The project begins in May.",
        "The budget excludes tax.",
        "Figures exclude sales tax.",
        *clauses,
    ]
    assert sent["evidence"][2]["table_data"] == table
    assert sent["evidence"][2]["pages"] == [1, 2]
    assert sent["evidence"][3]["parent_element_id"] == "costs"
    assert sent["evidence"][3]["kind"] == "caption"
    assert all(element["pages"] == [2] for element in sent["evidence"][4:])
    assert all(element["kind"] == "paragraph" for element in sent["evidence"][4:])
    saved = client.get(f"/revisions/{revision_id}/summary").json()
    assert saved["coverage"]["pages_without_content"] == [3]
    stored_table = client.get(f"/revisions/{revision_id}/evidence").json()["elements"][2]
    assert [location["page_no"] for location in stored_table["locations"]] == [1, 1, 2]
    assert stored_table["locations"][0]["x0"] == 50

    controls = client.get("/development/settings").json()
    response = client.put(
        "/development/settings",
        headers={"X-Folio-Development": "1"},
        json={
            "revision": controls["revision"],
            "values": {**controls["values"], "summary_input_limit_tokens": 2049},
        },
    )
    assert response.status_code == 200
    _, oversized = publish(with_table)
    url = f"/revisions/{oversized}/summary"
    before = len(model.calls)
    process_summary(client.get(url).json()["run_id"], settings=settings, client=model)
    refused = client.get(url).json()
    assert refused["state"] == "unavailable"
    assert len(model.calls) == before
    assert client.get(f"/revisions/{oversized}/evidence").status_code == 200


@pytest.mark.integration
def test_concurrent_work_cannot_reuse_reserved_global_or_document_allowance(
    summary_document, monkeypatch
):
    from folio.summaries.processing import process_summary

    settings, client, publish = summary_document
    monkeypatch.setenv("FOLIO_SUMMARY_BUDGET_USD", "0.02")
    _, first_revision = publish()
    _, second_revision = publish()
    first = client.get(f"/revisions/{first_revision}/summary").json()["run_id"]
    second_url = f"/revisions/{second_revision}/summary"
    second = client.get(second_url).json()["run_id"]
    started, release = Event(), Event()

    class Held(Model):
        def generate(self, messages, schema):
            result = super().generate(messages, schema)
            if len(self.calls) == 1:
                started.set()
                assert release.wait(10)
            return result

    model = Held()
    with ThreadPoolExecutor() as workers:
        active = workers.submit(process_summary, first, settings=settings, client=model)
        try:
            assert started.wait(5)
            assert process_summary(first, settings=settings, client=model)["outcome"] == "ignored"
            process_summary(second, settings=settings, client=model)
            refused = client.get(second_url).json()
            assert refused["state"] == "unavailable"
            assert refused["error"]["code"] == "SUMMARY_GLOBAL_BUDGET"
            assert len(model.calls) == 1
        finally:
            release.set()
        assert active.result(timeout=5)["outcome"] == "ready"

    monkeypatch.setenv("FOLIO_SUMMARY_DOCUMENT_BUDGET_USD", "0.001")
    _, third_revision = publish()
    third_url = f"/revisions/{third_revision}/summary"
    process_summary(client.get(third_url).json()["run_id"], settings=settings, client=model)
    assert client.get(third_url).json()["error"]["code"] == "SUMMARY_DOCUMENT_BUDGET"
    assert len(model.calls) == 1


@pytest.mark.integration
@pytest.mark.parametrize("budget,expected", [("0.04", "ready"), ("0.02", "unavailable")])
def test_expired_invocation_keeps_its_reservation_and_rejects_late_publication(
    summary_document, monkeypatch, budget, expected
):
    from folio.summaries.processing import process_summary

    settings, client, publish = summary_document
    monkeypatch.setenv("FOLIO_SUMMARY_BUDGET_USD", budget)
    _, revision_id = publish()
    url = f"/revisions/{revision_id}/summary"
    run_id = client.get(url).json()["run_id"]
    started, release = Event(), Event()

    class Held(Model):
        def generate(self, messages, schema):
            result = super().generate(messages, schema)
            started.set()
            assert release.wait(15)
            return result

    old_model, new_model = Held(), Model()
    with ThreadPoolExecutor() as workers:
        old = workers.submit(process_summary, run_id, settings=settings, client=old_model)
        try:
            assert started.wait(5)
            with psycopg.connect(settings.database_url) as connection:
                connection.execute(
                    "UPDATE summary_runs SET "
                    "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                    (run_id,),
                )
            from folio.summaries.dispatcher import dispatch_once

            dispatch_once(settings)
            recovered = client.get(url).json()
            assert recovered["state"] == "pending"
            assert Decimal(recovered["usage"]["uncertain_cost_usd"]) == Decimal("0.0152384")
            process_summary(run_id, settings=settings, client=new_model)
            completed = client.get(url).json()
            assert completed["state"] == expected
            assert len(new_model.calls) == (1 if expected == "ready" else 0)
        finally:
            release.set()
        assert old.result(timeout=5)["outcome"] == "superseded"
    assert client.get(url).json() == completed
    assert Decimal(completed["usage"]["uncertain_cost_usd"]) == Decimal("0.0152384")
    assert completed["usage"]["cost_usd"] is None


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["profile", "generation"])
def test_provider_timeout_retries_immediately_and_missing_credentials_never_reserve(
    summary_document, monkeypatch, stage
):
    from folio.ai.openrouter import ProviderError
    from folio.summaries.processing import process_summary

    settings, client, publish = summary_document
    _, revision_id = publish()
    url = f"/revisions/{revision_id}/summary"
    run_id = client.get(url).json()["run_id"]

    class Timeout(Model):
        def profile(self):
            if stage == "profile":
                raise ProviderError("SUMMARY_PROVIDER_TIMEOUT", retryable=True)
            return super().profile()

        def generate(self, messages, schema):
            raise ProviderError("SUMMARY_PROVIDER_TIMEOUT", retryable=True)

    process_summary(run_id, settings=settings, client=Timeout())
    pending = client.get(url).json()
    assert pending["state"] == "pending"
    assert Decimal(pending["usage"]["uncertain_cost_usd"]) == (
        Decimal("0.0152384") if stage == "generation" else Decimal(0)
    )
    process_summary(run_id, settings=settings, client=Model())
    assert client.get(url).json()["state"] == "ready"

    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    _, no_key_revision = publish()
    no_key_url = f"/revisions/{no_key_revision}/summary"
    process_summary(client.get(no_key_url).json()["run_id"], settings=settings)
    no_key = client.get(no_key_url).json()
    assert no_key["state"] == "unavailable"
    assert no_key["error"]["code"] == "SUMMARY_PROVIDER_NOT_CONFIGURED"
    assert Decimal(no_key["usage"]["uncertain_cost_usd"]) == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    "setting,value",
    [("FOLIO_SUMMARY_INPUT_LIMIT_TOKENS", "invalid"), ("FOLIO_SUMMARY_TOKEN_MARGIN", "0")],
)
def test_invalid_summary_configuration_preserves_published_extraction(
    summary_document, monkeypatch, setting, value
):
    settings, client, publish = summary_document
    monkeypatch.setenv(setting, value)
    receipt, revision_id = publish()
    status = client.get(receipt["status_url"]).json()
    assert status["state"] == "succeeded"
    summary = client.get(f"/revisions/{revision_id}/summary").json()
    assert summary["state"] == "unavailable"
    assert summary["error"]["code"] == "SUMMARY_CONFIGURATION_INVALID"
    assert summary["usage"]["attempts"] == 0
    assert client.get(f"/revisions/{revision_id}/evidence").status_code == 200


@pytest.mark.integration
def test_queue_loss_is_redelivered_and_preclaim_failures_are_bounded(summary_document):
    from rq.job import JobStatus

    from folio.ingestion.dispatcher import queue_for
    from folio.summaries.dispatcher import dispatch_once

    settings, client, publish = summary_document
    settings = settings.model_copy(update={"bootstrap_failure_limit": 2})
    receipt, revision_id = publish()
    url = f"/revisions/{revision_id}/summary"
    run_id = client.get(url).json()["run_id"]
    queue = queue_for(settings)
    try:
        delivered = dispatch_once(settings)[0]
        job = queue.fetch_job(delivered["job_id"])
        assert job.args[0] == run_id
        queue.remove(job.id)

        def due():
            with psycopg.connect(settings.database_url) as connection:
                connection.execute(
                    "UPDATE summary_runs SET next_dispatch_at=clock_timestamp() WHERE id=%s",
                    (run_id,),
                )

        due()
        replacement = dispatch_once(settings)[0]
        assert replacement["job_id"] != delivered["job_id"]
        for _ in range(2):
            job = queue.fetch_job(replacement["job_id"])
            queue.remove(job.id)
            job.set_status(JobStatus.FAILED)
            due()
            deliveries = dispatch_once(settings)
            if deliveries:
                replacement = deliveries[0]
        final = client.get(url).json()
        assert final["state"] == "failed"
        assert final["error"]["code"] == "SUMMARY_DELIVERY_FAILED"
        assert final["usage"]["attempts"] == 0
        assert client.get(receipt["status_url"]).json()["state"] == "succeeded"
    finally:
        queue.connection.close()


@pytest.mark.integration
def test_reading_disabled_or_existing_documents_never_schedules_work(summary_document, monkeypatch):
    settings, client, publish = summary_document
    monkeypatch.setenv("FOLIO_SUMMARY_ENABLED", "false")
    _, revision_id = publish()
    url = f"/revisions/{revision_id}/summary"
    disabled = client.get(url).json()
    assert disabled["state"] == "unavailable"
    assert disabled["error"]["code"] == "SUMMARY_DISABLED"
    monkeypatch.setenv("FOLIO_SUMMARY_ENABLED", "true")
    assert client.get(url).json() == disabled
    # Simulate an immutable extraction which predates summary intent publication.
    with psycopg.connect(settings.database_url) as connection:
        connection.execute("DELETE FROM summary_runs WHERE revision_id=%s", (revision_id,))
    assert client.get(url).json()["state"] == "not_scheduled"
    assert client.get(url).json()["run_id"] is None
    assert client.post(url).status_code == 405
