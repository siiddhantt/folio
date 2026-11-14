from datetime import datetime
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from folio.api import create_app
from folio.config import Settings
from folio.ingestion.parsing.evidence import Element, Extraction, ExtractionError, Location, Page
from folio.ingestion.processing import process_attempt


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_SUMMARY_ENABLED", "false")
    monkeypatch.setenv("FOLIO_INDEX_ENABLED", "false")
    settings = Settings(_env_file=None, artifact_root=tmp_path, development_mode=False)
    original = b"%PDF-1.4\nSynthetic monitoring input"
    with TestClient(create_app(settings)) as client:
        receipts = []
        for name in ("report.pdf", "pending.pdf"):
            headers = {"Idempotency-Key": str(uuid4())}
            files = {"file": (name, original)}
            response = client.post("/documents", headers=headers, files=files)
            assert response.status_code == 202
            receipts.append(response.json())
            assert client.post("/documents", headers=headers, files=files).json() == response.json()

        def parser(path, config):
            return Extraction(
                [
                    Page(1, 612, 792, "content_recovered"),
                    Page(2, 612, 792, "content_recovered"),
                    Page(3, 612, 792, "no_content_recovered"),
                ],
                [Element("p1", "paragraph", 0, None, "Total 48.", None, None, [Location(1)])],
                [],
                "success",
                {"fixture": True},
                {"text": "Total 48."},
                0.1,
            )

        request_id = receipts[0]["request_id"]
        attempt_id = client.get(f"/ingestion-requests/{request_id}").json()["authorized_attempt_id"]
        process_attempt(request_id, attempt_id, settings=settings, parser=parser)
        yield client, settings, receipts


@pytest.mark.integration
def test_document_statistics_describe_an_empty_library(tmp_path):
    settings = Settings(_env_file=None, artifact_root=tmp_path, development_mode=False)
    with TestClient(create_app(settings)) as client:
        response = client.get("/statistics/documents")
    assert response.status_code == 200
    result = response.json()
    assert datetime.fromisoformat(result.pop("as_of")).tzinfo is not None
    assert result == {
        "total_documents": 0,
        "original_bytes": 0,
        "extraction_states": {},
        "summary_states": {},
        "index_states": {},
        "pages": {
            "total": 0,
            "with_content": 0,
            "without_content": 0,
            "documents_without_extraction": 0,
        },
    }


@pytest.mark.integration
def test_statistics_count_documents_once_and_distinguish_unextracted_pages(library):
    client, settings, receipts = library
    # Historical originals do not increase current file bytes.
    with psycopg.connect(settings.database_url) as connection:
        connection.execute(
            """INSERT INTO file_versions
            (id,document_id,original_filename,media_type,byte_size,sha256,storage_key)
            VALUES (%s,%s,'old.pdf','application/pdf',9000,%s,'old.pdf')""",
            (uuid4(), receipts[0]["document_id"], "a" * 64),
        )
    result = client.get("/statistics/documents").json()
    assert result["total_documents"] == 2
    assert result["original_bytes"] == 70
    assert result["extraction_states"] == {"succeeded": 1, "open": 1}
    assert result["summary_states"] == {"unavailable": 1, "not_scheduled": 1}
    assert result["index_states"] == {"unavailable": 1, "not_started": 1}
    assert result["pages"] == {
        "total": 3,
        "with_content": 2,
        "without_content": 1,
        "documents_without_extraction": 1,
    }


@pytest.mark.integration
def test_metrics_separate_retried_jobs_from_attempts_and_exclude_missing_times(library):
    client, settings, receipts = library
    request_id = receipts[1]["request_id"]
    attempt_id = client.get(f"/ingestion-requests/{request_id}").json()["authorized_attempt_id"]

    def interrupted_parser(path, config):
        raise ExtractionError("IO_INTERRUPTED", "Synthetic interruption", retryable=True)

    process_attempt(request_id, attempt_id, settings=settings, parser=interrupted_parser)
    with psycopg.connect(settings.database_url) as connection:
        connection.execute(
            """UPDATE processing_attempts SET started_at='2026-01-01T00:00:00Z',
            finished_at='2026-01-01T00:00:10Z' WHERE state='succeeded'"""
        )
        connection.execute(
            """UPDATE processing_attempts SET started_at='2026-01-01T00:00:00Z',
            finished_at='2026-01-01T00:00:02Z' WHERE state='failed'"""
        )
    response = client.get("/metrics/processing")
    assert response.status_code == 200
    result = response.json()
    assert result["scope"] == "all_retained"
    assert set(result["stages"]) == {"extraction", "summary", "indexing", "chat", "memory"}
    assert result["stages"]["extraction"] == {
        "jobs": {"total": 2, "states": {"succeeded": 1, "open": 1}},
        "attempts": {
            "total": 3,
            "completed": 2,
            "unfinished": 1,
            "failed": 1,
            "duration_seconds": {"samples": 2, "mean": 6.0, "max": 10.0},
        },
        "terminal_errors": {},
    }
    assert result["stages"]["summary"]["jobs"] == {"total": 1, "states": {"unavailable": 1}}
    assert result["stages"]["summary"]["terminal_errors"] == {"SUMMARY_DISABLED": 1}
    assert result["stages"]["summary"]["attempts"]["duration_seconds"] == {
        "samples": 0,
        "mean": None,
        "max": None,
    }
    assert result["stages"]["chat"]["jobs"] == {"total": 0, "states": {}}


@pytest.mark.integration
def test_metrics_retain_removed_chat_work_and_count_batches_without_fanout(library):
    client, settings, receipts = library
    conversation_id, turn_id, memory_id = uuid4(), uuid4(), uuid4()
    with psycopg.connect(settings.database_url) as connection:
        index_id = connection.execute(
            "SELECT id FROM document_indexes WHERE document_id=%s", (receipts[0]["document_id"],)
        ).fetchone()[0]
        connection.execute("UPDATE document_indexes SET state='ready',error_code=NULL")
        for number in (1, 2):
            connection.execute(
                """INSERT INTO indexing_attempts
                (id,index_id,attempt_no,token,batch_no,state,started_at,finished_at)
                VALUES (%s,%s,%s,%s,%s,'succeeded',
                '2026-01-01T00:00:00Z','2026-01-01T00:00:05Z')""",
                (uuid4(), index_id, number, uuid4(), number),
            )
        # A retrying job can retain its previous error; it is not terminal.
        connection.execute("UPDATE summary_runs SET state='pending',error_code='SUMMARY_TIMEOUT'")
        connection.execute(
            """INSERT INTO summary_attempts
            (id,run_id,attempt_no,claim_token,started_at,finished_at,error_code)
            SELECT %s,id,1,%s,'2026-01-01T00:00:00Z','2026-01-01T00:00:03Z','SUMMARY_TIMEOUT'
            FROM summary_runs""",
            (uuid4(), uuid4()),
        )
        connection.execute(
            """INSERT INTO conversations (id,index_id,creation_key,deleted_at)
            VALUES (%s,%s,%s,now())""",
            (conversation_id, index_id, str(uuid4())),
        )
        connection.execute(
            """INSERT INTO conversation_turns
            (id,conversation_id,index_id,sequence,idempotency_key,question,policy,state,error_code)
            VALUES (%s,%s,%s,1,'one','What is the total?','{}','failed','CHAT_PROVIDER_TIMEOUT')""",
            (turn_id, conversation_id, index_id),
        )
        connection.execute(
            """INSERT INTO turn_attempts
            (id,turn_id,token,attempt_no,started_at,finished_at,error_code)
            VALUES (%s,%s,%s,1,'2026-01-01T00:00:00Z','2026-01-01T00:00:04Z',
            'CHAT_PROVIDER_TIMEOUT')""",
            (uuid4(), turn_id, uuid4()),
        )
        connection.execute(
            """INSERT INTO conversation_memories
            (id,conversation_id,index_id,covered_through,input,input_sha256,
            source_tokens,policy,state,error_code)
            VALUES (%s,%s,%s,1,'{}',%s,10,'{}','failed','MEMORY_TIMEOUT')""",
            (memory_id, conversation_id, index_id, "a" * 64),
        )
        connection.execute(
            """INSERT INTO memory_attempts
            (id,memory_id,attempt_no,token,reserved_usd,reserved_input,invoked_at,finished_at,error_code)
            VALUES (%s,%s,1,%s,0,10,'2026-01-01T00:00:00Z',
            '2026-01-01T00:00:02Z','MEMORY_TIMEOUT')""",
            (uuid4(), memory_id, uuid4()),
        )
    stages = client.get("/metrics/processing").json()["stages"]
    assert stages["indexing"]["jobs"] == {"total": 1, "states": {"ready": 1}}
    assert stages["indexing"]["attempts"] == {
        "total": 2,
        "completed": 2,
        "unfinished": 0,
        "failed": 0,
        "duration_seconds": {"samples": 2, "mean": 5.0, "max": 5.0},
    }
    assert stages["summary"]["terminal_errors"] == {}
    assert stages["summary"]["attempts"]["failed"] == 1
    assert stages["summary"]["attempts"]["duration_seconds"]["mean"] == 3.0
    assert stages["chat"]["jobs"] == {"total": 1, "states": {"failed": 1}}
    assert stages["chat"]["terminal_errors"] == {"CHAT_PROVIDER_TIMEOUT": 1}
    assert stages["chat"]["attempts"]["duration_seconds"]["mean"] == 4.0
    assert stages["memory"]["attempts"]["duration_seconds"]["mean"] == 2.0
    assert stages["memory"]["attempts"]["failed"] == 1
    assert stages["memory"]["jobs"] == {"total": 1, "states": {"failed": 1}}
    assert stages["memory"]["terminal_errors"] == {"MEMORY_TIMEOUT": 1}


@pytest.mark.integration
@pytest.mark.parametrize("started_at", [None, "2026-01-01T00:00:10Z"])
def test_completed_attempts_with_unusable_timing_do_not_become_zero_seconds(library, started_at):
    client, settings, receipts = library
    with psycopg.connect(settings.database_url) as connection:
        connection.execute(
            """UPDATE processing_attempts SET started_at=%s,finished_at='2026-01-01T00:00:02Z'
            WHERE state='succeeded'""",
            (started_at,),
        )
    attempts = client.get("/metrics/processing").json()["stages"]["extraction"]["attempts"]
    assert attempts["completed"] == 1
    assert attempts["unfinished"] == 1
    assert attempts["duration_seconds"] == {"samples": 0, "mean": None, "max": None}
