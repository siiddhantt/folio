from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue
from rq.job import Job, JobStatus
from rq.serializers import JSONSerializer

from folio.api import create_app
from folio.config import Settings


@pytest.mark.integration
def test_dispatcher_delivers_accepted_work_without_the_api_process(tmp_path):
    from folio.ingestion.dispatcher import dispatch_once

    settings = Settings(artifact_root=tmp_path)
    with TestClient(create_app(settings)) as client:
        accepted = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", b"%PDF-1.4\npending test")},
        ).json()
    deliveries = dispatch_once(settings)
    delivery = next(item for item in deliveries if item["request_id"] == accepted["request_id"])
    job = Job.fetch(
        delivery["job_id"], connection=Redis.from_url(settings.redis_url), serializer=JSONSerializer
    )
    assert job.args[0] == accepted["request_id"]
    assert job.get_status().value == "queued"


@pytest.mark.integration
def test_recovery_detects_queue_loss_and_bounds_preclaim_failures(tmp_path):
    from folio.ingestion.dispatcher import dispatch_once

    settings = Settings(artifact_root=tmp_path, bootstrap_failure_limit=2)
    redis = Redis.from_url(settings.redis_url)
    queue = Queue("ingestion", connection=redis, serializer=JSONSerializer)
    with TestClient(create_app(settings)) as client:
        accepted = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", b"%PDF-1.4\nqueue-loss input")},
        ).json()
        first = dispatch_once(settings)[0]
        queue.remove(first["job_id"])

        def make_due():
            with psycopg.connect(settings.database_url) as connection:
                connection.execute(
                    "UPDATE processing_attempts SET next_dispatch_at=now() WHERE request_id=%s",
                    (accepted["request_id"],),
                )

        make_due()
        replaced = dispatch_once(settings)
        assert len(replaced) == 1
        assert replaced[0]["job_id"] != first["job_id"]
        for _ in range(2):
            job = queue.fetch_job(replaced[0]["job_id"])
            queue.remove(job.id)
            job.set_status(JobStatus.FAILED)
            make_due()
            replaced = dispatch_once(settings)
        status = client.get(accepted["status_url"]).json()
        assert status["state"] == "failed"
        assert status["attempts"][0]["error_code"] == "DELIVERY_FAILED"
        assert len(status["attempts"]) == 1


@pytest.mark.integration
def test_inspecting_healthy_queued_work_preserves_actual_dispatch_time(tmp_path):
    from folio.ingestion.dispatcher import dispatch_once

    settings = Settings(artifact_root=tmp_path, development_mode=True)
    with TestClient(create_app(settings)) as client:
        accepted = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", b"%PDF-1.4\nqueued work")},
        ).json()
        dispatch_once(settings)
        url = f"/development/ingestion-requests/{accepted['request_id']}"
        first = client.get(url).json()["attempts"][0]
        assert first["last_dispatched_at"] is not None
        with psycopg.connect(settings.database_url) as connection:
            connection.execute(
                "UPDATE processing_attempts SET next_dispatch_at=now() WHERE request_id=%s",
                (accepted["request_id"],),
            )
        assert dispatch_once(settings) == []
        inspected = client.get(url).json()["attempts"][0]
        assert inspected["last_dispatched_at"] == first["last_dispatched_at"]
        assert inspected["transport_job_id"] == first["transport_job_id"]
        assert inspected["dispatch_count"] == first["dispatch_count"]
