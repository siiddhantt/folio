import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from folio.api import create_app
from folio.config import Settings


@pytest.mark.integration
def test_capabilities_disclose_limits_and_development_view_is_disabled_by_default():
    with TestClient(create_app(Settings(_env_file=None, max_pages=12))) as client:
        response = client.get("/capabilities")
        assert response.status_code == 200
        assert response.json() == {
            "max_upload_bytes": 26214400,
            "max_pages": 12,
            "development_mode": False,
        }
        assert client.get(f"/development/ingestion-requests/{uuid4()}").status_code == 404


@pytest.mark.integration
def test_development_view_has_durable_acceptance_without_private_configuration(tmp_path):
    settings = Settings(artifact_root=tmp_path, development_mode=True)
    original = b"%PDF-1.4\ncontrolled admission input"
    with TestClient(create_app(settings)) as client:
        receipt = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", original)},
        ).json()
        response = client.get(f"/development/ingestion-requests/{receipt['request_id']}")
        assert response.status_code == 200
        details = response.json()
        assert details["source"]["byte_size"] == len(original)
        assert len(details["source"]["sha256"]) == 64
        assert details["configuration"]["parser"] == "docling"
        assert "models_path" not in details["configuration"]
        assert "storage_key" not in details["source"]
        assert "claim_token" not in details["attempts"][0]
        assert details["authorized_attempt_id"] == details["attempts"][0]["id"]
        assert [event["name"] for event in details["events"]] == ["accepted"]
        assert details["events"][0]["occurred_at"]
        assert details["next_after_id"] is None
        missing = client.get(f"/development/ingestion-requests/{uuid4()}")
        assert missing.status_code == 404


@pytest.mark.integration
def test_development_view_follows_actual_processing_and_paginates_events(tmp_path):
    from folio.ingestion.parsing.evidence import Element, Extraction, Location, Page
    from folio.ingestion.processing import process_attempt

    settings = Settings(artifact_root=tmp_path, development_mode=True)
    with TestClient(create_app(settings)) as client:
        receipt = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", b"%PDF-1.4\ncontrolled parser input")},
        ).json()
        url = f"/development/ingestion-requests/{receipt['request_id']}"
        attempt = client.get(receipt["status_url"]).json()["authorized_attempt_id"]

        def parser(path, config):
            during = client.get(url).json()
            assert during["state"] == "open"
            assert during["attempts"][0]["state"] == "running"
            assert during["events"][-1]["name"] == "parse_started"
            return Extraction(
                [Page(1, 612, 792, "content_recovered")],
                [Element("p1", "paragraph", 0, None, "Revenue was 48.", None, None, [Location(1)])],
                [],
                "success",
                {"fixture": True},
                {"text": "Revenue was 48."},
                0.1,
            )

        process_attempt(receipt["request_id"], attempt, settings=settings, parser=parser)
        final = client.get(url).json()
        assert final["state"] == "succeeded"
        names = [event["name"] for event in final["events"]]
        assert names == [
            "accepted",
            "worker_claimed",
            "source_verified",
            "parse_started",
            "parse_completed",
            "raw_result_saved",
            "published",
        ]
        completed = next(event for event in final["events"] if event["name"] == "parse_completed")
        assert completed["details"]["duration_seconds"] >= 0
        assert completed["details"]["pages"] == 1
        assert completed["details"]["elements"] == 1
        first = client.get(url, params={"limit": 2}).json()
        next_page = client.get(url, params={"after_id": first["next_after_id"], "limit": 2}).json()
        assert [e["id"] for e in first["events"] + next_page["events"]] == [
            e["id"] for e in final["events"][:4]
        ]
        assert client.get(url, params={"limit": 201}).status_code == 422


@pytest.mark.integration
def test_failed_parse_has_no_completion_and_records_authorized_retry(tmp_path):
    from folio.ingestion.processing import process_attempt

    settings = Settings(
        artifact_root=tmp_path,
        development_mode=True,
        retry_delays_seconds=(0,),
        retry_jitter_seconds=0,
    )
    with TestClient(create_app(settings)) as client:
        receipt = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", b"%PDF-1.4\ncontrolled failure input")},
        ).json()
        url = f"/development/ingestion-requests/{receipt['request_id']}"
        attempt = client.get(receipt["status_url"]).json()["authorized_attempt_id"]

        def interrupted(path, config):
            raise OSError("Controlled external interruption")

        process_attempt(receipt["request_id"], attempt, settings=settings, parser=interrupted)
        details = client.get(url).json()
        assert details["state"] == "open"
        assert [a["state"] for a in details["attempts"]] == ["failed", "pending"]
        assert details["authorized_attempt_id"] == details["attempts"][1]["id"]
        assert "parse_completed" not in [e["name"] for e in details["events"]]
        failure, retry = details["events"][-2:]
        assert failure["name"] == "attempt_failed"
        assert failure["details"]["error_code"] == "IO_INTERRUPTED"
        assert retry["name"] == "retry_scheduled"
        assert retry["attempt_id"] == details["authorized_attempt_id"]


@pytest.mark.integration
def test_original_can_be_previewed_without_changing_download_behavior(tmp_path):
    original = b"%PDF-1.4\nimmutable original input"
    with TestClient(create_app(Settings(artifact_root=tmp_path))) as client:
        receipt = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", original)},
        ).json()
        url = f"/documents/{receipt['document_id']}/original"
        assert client.get(url).headers["content-disposition"].startswith("attachment;")
        preview = client.get(url, params={"inline": "true"})
        assert preview.headers["content-disposition"].startswith("inline;")
        assert preview.content == original


@pytest.mark.integration
def test_delivery_outage_is_observed_without_spending_a_processing_attempt(tmp_path):
    from folio.ingestion.dispatcher import dispatch_once

    settings = Settings(
        artifact_root=tmp_path, development_mode=True, redis_url="redis://127.0.0.1:1/15"
    )
    with TestClient(create_app(settings)) as client:
        receipt = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", b"%PDF-1.4\ncontrolled admission input")},
        ).json()
        dispatch_once(settings)
        result = client.get(f"/development/ingestion-requests/{receipt['request_id']}").json()
        assert result["state"] == "open"
        assert len(result["attempts"]) == 1
        assert result["attempts"][0]["state"] == "pending"
        assert result["attempts"][0]["dispatch_error"] == "ConnectionError"
        assert result["events"][-1]["name"] == "delivery_deferred"
        assert result["events"][-1]["details"]["error_code"] == "ConnectionError"


@pytest.mark.integration
def test_unavailable_event_storage_does_not_erase_known_failure(tmp_path):
    from folio.ingestion.parsing.evidence import ExtractionError
    from folio.ingestion.processing import process_attempt

    settings = Settings(artifact_root=tmp_path, development_mode=True)
    with psycopg.connect(settings.database_url) as connection:
        connection.execute(
            "ALTER TABLE processing_events ADD CONSTRAINT unavailable_in_test "
            "CHECK(false) NOT VALID"
        )
    try:
        with TestClient(create_app(settings)) as client:
            receipt = client.post(
                "/documents",
                headers={"Idempotency-Key": str(uuid4())},
                files={"file": ("report.pdf", b"%PDF-1.4\ncontrolled admission input")},
            ).json()
            attempt = client.get(receipt["status_url"]).json()["authorized_attempt_id"]

            def unreadable(path, config):
                raise ExtractionError("NO_USABLE_CONTENT", "No readable source evidence")

            process_attempt(receipt["request_id"], attempt, settings=settings, parser=unreadable)
            status = client.get(receipt["status_url"]).json()
            assert status["state"] == "failed"
            assert status["attempts"][0]["error_code"] == "NO_USABLE_CONTENT"
            details = client.get(f"/development/ingestion-requests/{receipt['request_id']}").json()
            assert details["events"] == []
    finally:
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("ALTER TABLE processing_events DROP CONSTRAINT unavailable_in_test")


@pytest.mark.integration
def test_clean_api_dispatcher_and_worker_emit_correlated_structured_logs(tmp_path):
    environment = {
        **os.environ,
        "FOLIO_ARTIFACT_ROOT": str(tmp_path),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    }
    api = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
from fastapi.testclient import TestClient
from folio.api import create_app
create_app()
with TestClient(create_app()) as client:
    receipt = client.post('/documents', headers={'Idempotency-Key': 'log-test'},
        files={'file': ('report.pdf', b'%PDF-1.4 controlled input')}).json()
    receipt['attempt_id'] = client.get(receipt['status_url']).json()['authorized_attempt_id']
    print(json.dumps(receipt))
""",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    receipt = json.loads(api.stdout)
    dispatcher = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from folio.config import Settings
from folio.ingestion.dispatcher import dispatch_once
dispatch_once(Settings(redis_url='redis://127.0.0.1:1/15'))
""",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    worker = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from folio.ingestion.parsing.evidence import ExtractionError
from folio.ingestion.processing import process_attempt
def unreadable(path, config):
    raise ExtractionError('NO_USABLE_CONTENT', 'No readable source evidence')
process_attempt(sys.argv[1], sys.argv[2], parser=unreadable)
""",
            receipt["request_id"],
            receipt["attempt_id"],
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    events = [
        json.loads(line)
        for line in (api.stderr + dispatcher.stderr + worker.stderr).splitlines()
        if line.startswith("{")
    ]
    names = [event["event"] for event in events]
    assert names.count("upload_receipt") == 1
    assert names.count("processing_started") == 1
    assert names.count("delivery_deferred") == 1
    assert names.count("attempt_failed") == 1
    assert {event["component"] for event in events} == {"api", "dispatcher", "worker"}
    assert len({event["pid"] for event in events}) == 3
    for event in events:
        assert datetime.fromisoformat(event["timestamp"]).utcoffset() == timedelta(0)
        assert event["severity"] in {"INFO", "WARNING", "ERROR"}
        assert isinstance(event["pid"], int) and event["pid"] > 0
    deferred = next(event for event in events if event["event"] == "delivery_deferred")
    assert deferred["severity"] == "WARNING"
    assert deferred["error_type"] == "ConnectionError"
    assert all(event["request_id"] == receipt["request_id"] for event in events)
    assert all(
        event["attempt_id"] == receipt["attempt_id"]
        for event in events
        if event["event"] != "upload_receipt"
    )


@pytest.mark.integration
def test_unexpected_processing_error_is_diagnosable_without_private_exception_text(tmp_path):
    settings = Settings(artifact_root=tmp_path)
    private_text = "PRIVATE_DOCUMENT_SENTINEL password=private-value"
    with TestClient(create_app(settings)) as client:
        receipt = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("private-report.pdf", b"%PDF-1.4 controlled failure")},
        ).json()
        attempt = client.get(receipt["status_url"]).json()["authorized_attempt_id"]
        worker = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
from folio.ingestion.processing import process_attempt
def broken_parser(path, config):
    raise ValueError(sys.argv[3])
process_attempt(sys.argv[1], sys.argv[2], parser=broken_parser)
""",
                receipt["request_id"],
                attempt,
                private_text,
            ],
            env={
                **os.environ,
                "FOLIO_ARTIFACT_ROOT": str(tmp_path),
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
            },
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        status = client.get(receipt["status_url"]).json()
        assert status["state"] == "failed"
        assert status["revision_id"] is None
        assert status["attempts"][0]["error_code"] == "PROCESSING_ERROR"
        assert status["attempts"][0]["error_detail"] == "ValueError"
    assert "PRIVATE_DOCUMENT_SENTINEL" not in worker.stderr
    assert "private-value" not in worker.stderr
    assert "private-report.pdf" not in worker.stderr
    assert str(tmp_path) not in worker.stderr
    records = [json.loads(line) for line in worker.stderr.splitlines() if line.startswith("{")]
    errors = [record for record in records if record["event"] == "processing_error"]
    assert len(errors) == 1
    error = errors[0]
    assert error["request_id"] == receipt["request_id"]
    assert error["attempt_id"] == attempt
    assert error["severity"] == "ERROR"
    assert error["error_type"] == "ValueError"
    assert error["operation"] == "parse"
    assert 1 <= len(error["error_frames"]) <= 8
    for frame in error["error_frames"]:
        assert set(frame) == {"module", "function", "line"}
        assert frame["module"].startswith("folio.")
        assert frame["function"] and isinstance(frame["line"], int) and frame["line"] > 0
    assert not any(record["event"] == "processing_finished" for record in records)
