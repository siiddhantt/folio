from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from folio.api import create_app
from folio.config import Settings
from folio.ingestion.parsing.evidence import Element, Extraction, Location, Page
from folio.ingestion.processing import process_attempt


def recovered_text(path, config):
    return Extraction(
        [Page(1, 612, 792, "content_recovered")],
        [Element("p1", "paragraph", 0, None, "Renewal is October 12.", None, None, [Location(1)])],
        [],
        "success",
        {"fixture": True},
        {"text": "Renewal is October 12."},
        0.1,
    )


@pytest.fixture
def accepted(tmp_path):
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
        yield settings, client, receipt


@pytest.mark.integration
def test_storage_setup_failure_is_recorded_without_waiting_for_recovery(accepted):
    settings, client, receipt = accepted
    unavailable = settings.artifact_root / "unavailable-storage"
    unavailable.write_text("A file cannot be used as the artifact directory.")
    attempt = client.get(receipt["status_url"]).json()["authorized_attempt_id"]

    process_attempt(
        receipt["request_id"],
        attempt,
        settings=settings.model_copy(update={"artifact_root": unavailable}),
        parser=recovered_text,
    )

    status = client.get(receipt["status_url"]).json()
    assert status["state"] == "open"
    assert [item["state"] for item in status["attempts"]] == ["failed", "pending"]
    assert status["attempts"][0]["error_code"] == "IO_INTERRUPTED"
    assert status["attempts"][0]["retryable"] is True
    assert status["authorized_attempt_id"] == status["attempts"][1]["id"]
    assert client.get(f"/documents/{receipt['document_id']}/original").status_code == 200


@pytest.mark.integration
def test_transient_failure_retries_then_publishes_once(accepted):
    settings, client, receipt = accepted
    initial = client.get(receipt["status_url"]).json()

    def unavailable(path, config):
        raise OSError("Temporary I/O interruption")

    process_attempt(
        receipt["request_id"], initial["attempts"][0]["id"], settings=settings, parser=unavailable
    )
    retrying = client.get(receipt["status_url"]).json()
    assert retrying["state"] == "open"
    assert [a["state"] for a in retrying["attempts"]] == ["failed", "pending"]
    second = retrying["attempts"][1]["id"]
    result = process_attempt(
        receipt["request_id"], second, settings=settings, parser=recovered_text
    )
    duplicate = process_attempt(
        receipt["request_id"], second, settings=settings, parser=unavailable
    )
    assert duplicate["outcome"] == "ignored"
    final = client.get(receipt["status_url"]).json()
    assert final["state"] == "succeeded"
    assert final["revision_id"] == result["revision_id"]


@pytest.mark.integration
@pytest.mark.parametrize("late_failure", [False, True])
def test_expired_worker_cannot_overwrite_recovered_result(accepted, late_failure):
    from folio.ingestion.dispatcher import dispatch_once

    settings, client, receipt = accepted
    started, release = Event(), Event()

    def delayed(path, config):
        started.set()
        assert release.wait(15), "Test did not release controlled worker"
        if late_failure:
            raise OSError("Late failure after ownership expired")
        return recovered_text(path, config)

    first = client.get(receipt["status_url"]).json()["attempts"][0]["id"]
    with ThreadPoolExecutor() as workers:
        old = workers.submit(
            process_attempt, receipt["request_id"], first, settings=settings, parser=delayed
        )
        try:
            assert started.wait(10)
            # Inject passage of lease time without waiting seven minutes in a test.
            with psycopg.connect(settings.database_url) as connection:
                connection.execute(
                    "UPDATE processing_attempts SET lease_expires_at=now()-interval '1 second' "
                    "WHERE id=%s",
                    (first,),
                )
            dispatch_once(settings)
            retrying = client.get(receipt["status_url"]).json()
            assert len(retrying["attempts"]) == 2
            second = retrying["attempts"][1]["id"]
            result = process_attempt(
                receipt["request_id"], second, settings=settings, parser=recovered_text
            )
        finally:
            release.set()
        old.result(timeout=10)
    final = client.get(receipt["status_url"]).json()
    assert final["state"] == "succeeded"
    assert final["revision_id"] == result["revision_id"]
    assert [a["state"] for a in final["attempts"]] == ["failed", "succeeded"]
    inspected = client.get(f"/development/ingestion-requests/{receipt['request_id']}").json()
    assert inspected["attempts"][0]["error_code"] == "WORKER_LOST"
    assert all(attempt["failure_diagnostics"] is None for attempt in inspected["attempts"])


@pytest.mark.integration
def test_diagnostic_export_failure_preserves_the_known_terminal_outcome(accepted):
    from folio.ingestion.parsing.evidence import ExtractionError

    settings, client, receipt = accepted
    attempt = client.get(receipt["status_url"]).json()["attempts"][0]["id"]

    def unusable(path, config):
        raise ExtractionError(
            "NO_USABLE_CONTENT",
            "No readable source evidence",
            raw={"unsupported_number": float("nan")},
        )

    process_attempt(receipt["request_id"], attempt, settings=settings, parser=unusable)
    final = client.get(receipt["status_url"]).json()
    assert final["state"] == "failed"
    assert final["attempts"][0]["error_code"] == "NO_USABLE_CONTENT"
    assert len(final["attempts"]) == 1


@pytest.mark.integration
def test_duplicate_workers_only_one_can_process(accepted):
    settings, client, receipt = accepted
    attempt = client.get(receipt["status_url"]).json()["attempts"][0]["id"]
    started, release = Event(), Event()

    def delayed(path, config):
        started.set()
        assert release.wait(10)
        return recovered_text(path, config)

    with ThreadPoolExecutor() as workers:
        first = workers.submit(
            process_attempt, receipt["request_id"], attempt, settings=settings, parser=delayed
        )
        try:
            assert started.wait(5)
            duplicate = process_attempt(
                receipt["request_id"], attempt, settings=settings, parser=recovered_text
            )
            assert duplicate["outcome"] == "ignored"
        finally:
            release.set()
        assert first.result(timeout=10)["outcome"] == "published"
    assert len(client.get(receipt["status_url"]).json()["attempts"]) == 1


@pytest.mark.integration
def test_retry_budget_exhaustion_is_visible(accepted):
    settings, client, receipt = accepted

    def unavailable(path, config):
        raise OSError("Temporary I/O interruption")

    for _ in range(3):
        attempt = client.get(receipt["status_url"]).json()["attempts"][-1]["id"]
        process_attempt(receipt["request_id"], attempt, settings=settings, parser=unavailable)
    final = client.get(receipt["status_url"]).json()
    assert final["state"] == "failed"
    assert len(final["attempts"]) == 3
    assert final["revision_id"] is None
