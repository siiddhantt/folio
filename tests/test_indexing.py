from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from folio.api import create_app
from folio.config import Settings
from folio.ingestion.parsing.evidence import Extraction, Page
from folio.ingestion.processing import process_attempt


def extracted_document(path, config):
    from docling_core.types.doc import BoundingBox, DocItemLabel, DoclingDocument, ProvenanceItem

    from folio.ingestion.parsing.parser import _elements

    document = DoclingDocument(name="Synthetic two-section document")
    for page, heading, text in (
        (1, "Coverage", "Garage cover reduces the building limit."),
        (2, "Exceptions", "Commercial use is excluded."),
    ):

        def location(text, page=page):
            return ProvenanceItem(
                page_no=page,
                charspan=(0, len(text)),
                bbox=BoundingBox(l=10, t=10, r=300, b=40, coord_origin="TOPLEFT"),
            )

        document.add_heading(text=heading, prov=location(heading))
        document.add_text(label=DocItemLabel.TEXT, text=text, prov=location(text))
    raw = document.export_to_dict()
    pages = {str(p): {"size": {"width": 612, "height": 792}} for p in (1, 2)}
    return Extraction(
        [Page(p, 612, 792, "content_recovered") for p in (1, 2)],
        _elements(raw, pages, []),
        [],
        "success",
        {"fixture": True},
        raw,
        0.1,
    )


class Embeddings:
    def __init__(self, cost="0.0000004"):
        self.calls = []
        self.cost = Decimal(cost)

    def profile(self):
        return {
            "model_id": "openai/text-embedding-3-small",
            "provider": "openai",
            "input_price_per_million": "0.02",
            "dimensions": 1536,
            "max_input_tokens": 8192,
        }

    def embed(self, texts):
        self.calls.append(texts)
        return SimpleNamespace(
            vectors=[[1.0] + [0.0] * 1535 for _ in texts],
            metadata={
                "model": "openai/text-embedding-3-small",
                "prompt_tokens": 20,
                "response_id": "synthetic-response",
            },
            cost_usd=self.cost,
        )


@pytest.fixture
def indexed_document(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_SUMMARY_ENABLED", "false")
    monkeypatch.setenv("FOLIO_INDEX_ENABLED", "true")
    monkeypatch.setenv("FOLIO_INDEX_BATCH_SIZE", "1")
    monkeypatch.setenv("FOLIO_SUMMARY_BUDGET_USD", "1")
    monkeypatch.setenv("FOLIO_SUMMARY_DOCUMENT_BUDGET_USD", "0.40")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    settings = Settings(
        _env_file=None,
        artifact_root=tmp_path,
        development_mode=True,
        retry_delays_seconds=(0,),
        retry_jitter_seconds=0,
    )
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        receipt = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("source.pdf", b"%PDF-1.4\nSynthetic input")},
        ).json()
        status = client.get(receipt["status_url"]).json()
        result = process_attempt(
            receipt["request_id"],
            status["authorized_attempt_id"],
            settings=settings,
            parser=extracted_document,
        )
        yield settings, client, result["revision_id"]


@pytest.mark.integration
@pytest.mark.parser
@pytest.mark.parametrize("cost", ["0.0000004", "0.01"])
def test_batches_become_readable_only_after_complete_index_and_replays_reuse_it(
    indexed_document, cost
):
    settings, client, revision = indexed_document
    url = f"/revisions/{revision}/index"
    pending = client.get(url)
    assert pending.status_code == 200
    assert pending.json()["state"] == "pending"

    from folio.indexing.processing import process_index

    model = Embeddings(cost)
    index_id = pending.json()["index_id"]
    assert process_index(index_id, settings=settings, client=model)["outcome"] == "pending"
    assert client.get(url).json()["embedded_chunks"] == 1
    assert client.get(url + "/chunks").status_code == 409
    if cost == "0.01":
        assert process_index(index_id, settings=settings, client=model)["outcome"] == "unavailable"
        assert client.get(url).json()["error_code"] == "INDEX_RESERVATION_EXCEEDED"
        runtime = client.get("/development/settings").json()["runtime"]
        assert Decimal(runtime["spent_usd"]) == Decimal("0.01")
        assert runtime["admission_error"] == "RESERVATION_EXCEEDED"
        assert len(model.calls) == 1
        return
    assert process_index(index_id, settings=settings, client=model)["outcome"] == "ready"
    chunks = client.get(url + "/chunks").json()["chunks"]
    assert len(chunks) == 2
    assert "Garage cover reduces" in chunks[0]["text"]
    assert {s["page_no"] for s in chunks[0]["sources"]} == {1}
    assert "Commercial use is excluded." in chunks[1]["text"]
    assert len(model.calls) == 2
    assert process_index(index_id, settings=settings, client=model)["outcome"] == "ignored"
    assert client.post(url).json()["index_id"] == index_id
    assert len(model.calls) == 2


@pytest.mark.integration
@pytest.mark.parser
def test_queue_outage_keeps_index_intent_for_later_delivery(indexed_document):
    from folio.indexing.dispatcher import dispatch_once
    from folio.ingestion.dispatcher import queue_for

    settings, client, revision = indexed_document
    url = f"/revisions/{revision}/index"
    index_id = client.get(url).json()["index_id"]
    unavailable = settings.model_copy(update={"redis_url": "redis://127.0.0.1:1/0"})
    assert dispatch_once(unavailable) == []
    assert client.get(url).json()["state"] == "pending"
    assert client.get(url).json()["dispatch_error"]
    with psycopg.connect(settings.database_url) as conn:
        conn.execute("UPDATE document_indexes SET next_dispatch_at=now() WHERE id=%s", (index_id,))
    (delivery,) = dispatch_once(settings)
    queue = queue_for(settings)
    try:
        job = queue.fetch_job(delivery["job_id"])
        assert job.args[0] == index_id
        assert job.get_status().value == "queued"
        job.delete()
    finally:
        queue.connection.close()


@pytest.mark.integration
@pytest.mark.parser
def test_lost_worker_resumes_only_missing_batch_and_late_charge_is_kept(indexed_document):
    from folio.database import Database
    from folio.indexing.lifecycle import recover_expired
    from folio.indexing.processing import process_index

    settings, client, revision = indexed_document
    url = f"/revisions/{revision}/index"
    index_id = client.get(url).json()["index_id"]
    model = Embeddings()
    process_index(index_id, settings=settings, client=model)

    class LateResponse(Embeddings):
        def embed(self, texts):
            result = super().embed(texts)
            with psycopg.connect(settings.database_url) as conn:
                conn.execute(
                    "UPDATE document_indexes SET lease_expires_at=now()-interval '1 second' "
                    "WHERE id=%s",
                    (index_id,),
                )
            database = Database(settings.database_url)
            database.open()
            try:
                recover_expired(database)
            finally:
                database.close()
            return result

    late = LateResponse()
    assert process_index(index_id, settings=settings, client=late)["outcome"] == "superseded"
    assert client.get(url).json()["embedded_chunks"] == 1
    request_id = client.get(f"/revisions/{revision}/evidence").json()["request_id"]
    inspection = client.get(f"/development/ingestion-requests/{request_id}").json()["indexing"]
    assert inspection["attempts"][-1]["billing_state"] == "known"
    assert Decimal(str(inspection["attempts"][-1]["cost_usd"])) == Decimal("0.0000004")
    assert process_index(index_id, settings=settings, client=model)["outcome"] == "ready"
    assert model.calls[-1] == late.calls[0]
    assert model.calls[0] != late.calls[0]
    assert process_index(index_id, settings=settings, client=model)["outcome"] == "ignored"
    assert client.post(url).json()["index_id"] == index_id
    assert len(model.calls) == 2


@pytest.mark.integration
@pytest.mark.parser
def test_timeouts_hold_unknown_charges_and_stop_after_bounded_retries(indexed_document):
    from folio.indexing.processing import process_index
    from folio.indexing.provider import EmbeddingError

    settings, client, revision = indexed_document
    url = f"/revisions/{revision}/index"
    index_id = client.get(url).json()["index_id"]

    class Timeout(Embeddings):
        def embed(self, texts):
            raise EmbeddingError("EMBEDDING_TIMEOUT", retryable=True)

    assert process_index(index_id, settings=settings, client=Timeout())["outcome"] == "pending"
    assert process_index(index_id, settings=settings, client=Timeout())["outcome"] == "failed"
    assert process_index(index_id, settings=settings, client=Timeout())["outcome"] == "ignored"
    request_id = client.get(f"/revisions/{revision}/evidence").json()["request_id"]
    attempts = client.get(f"/development/ingestion-requests/{request_id}").json()["indexing"][
        "attempts"
    ]
    assert len(attempts) == 2
    assert all(a["billing_state"] == "unknown" and a["reserved_usd"] > 0 for a in attempts)
    assert client.get(url).json()["embedded_chunks"] == 0
    assert client.get(url + "/chunks").status_code == 409
