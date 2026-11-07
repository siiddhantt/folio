from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from folio.api import create_app
from folio.config import Settings


@pytest.mark.integration
def test_accepted_pdf_has_durable_status_and_original(tmp_path):
    settings = Settings(artifact_root=tmp_path)
    original = b"%PDF-1.4\nsynthetic admission fixture; extraction tested separately"
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", original, "application/pdf")},
        )
        assert response.status_code == 202
        accepted = response.json()
        status = client.get(accepted["status_url"]).json()
        assert status["state"] == "open"
        assert status["attempts"][0]["state"] == "pending"
        downloaded = client.get(f"/documents/{accepted['document_id']}/original")
        assert downloaded.content == original


@pytest.mark.integration
def test_processed_pdf_publishes_inspectable_evidence(tmp_path):
    from folio.parsing.evidence import Element, Extraction, Location, Page
    from folio.processing import process_attempt

    def parser(path, config):
        return Extraction(
            pages=[Page(1, 612, 792, "content_recovered")],
            elements=[
                Element(
                    "p1", "paragraph", 0, None, "Revenue was 48 million.", None, None, [Location(1)]
                )
            ],
            diagnostics=[],
            parser_status="success",
            parser_manifest={"test_fixture": True},
            raw={"source": "controlled parser result"},
            duration_seconds=0.1,
        )

    settings = Settings(artifact_root=tmp_path)
    with TestClient(create_app(settings)) as client:
        accepted = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", b"%PDF-1.4\ncontrolled parser input")},
        ).json()
        attempt = client.get(accepted["status_url"]).json()["attempts"][0]["id"]
        process_attempt(accepted["request_id"], attempt, settings=settings, parser=parser)
        status = client.get(accepted["status_url"]).json()
        assert status["state"] == "succeeded"
        evidence = client.get(f"/revisions/{status['revision_id']}/evidence").json()
        assert evidence["elements"][0]["text"] == "Revenue was 48 million."
        assert evidence["elements"][0]["locations"][0]["page_no"] == 1


@pytest.mark.integration
def test_concurrent_retries_replay_and_different_input_conflicts(tmp_path):
    settings = Settings(artifact_root=tmp_path)
    key = str(uuid4())
    original = b"%PDF-1.4\noriginal content"
    with TestClient(create_app(settings)) as client:

        def upload():
            return client.post(
                "/documents",
                headers={"Idempotency-Key": key},
                files={"file": ("report.pdf", original)},
            )

        with ThreadPoolExecutor(max_workers=4) as callers:
            responses = list(callers.map(lambda _: upload(), range(4)))
        assert all(response.status_code == 202 for response in responses)
        assert len({response.json()["document_id"] for response in responses}) == 1
        receipt = responses[0].json()
        conflict = client.post(
            "/documents",
            headers={"Idempotency-Key": key},
            files={"file": ("report.pdf", b"%PDF-1.4\nchanged content")},
        )
        assert conflict.status_code == 409
        assert client.get(f"/documents/{receipt['document_id']}/original").content == original
    with TestClient(create_app(settings.model_copy(update={"max_pages": 50}))) as restarted:
        replay = restarted.post(
            "/documents", headers={"Idempotency-Key": key}, files={"file": ("report.pdf", original)}
        )
        assert replay.json() == receipt


@pytest.mark.integration
def test_upload_limits_and_filename_cannot_control_storage_path(tmp_path):
    settings = Settings(artifact_root=tmp_path, max_upload_bytes=50)
    with TestClient(create_app(settings)) as client:
        headers = {"Idempotency-Key": str(uuid4())}
        invalid = client.post(
            "/documents", headers=headers, files={"file": ("x.pdf", b"not a PDF")}
        )
        assert invalid.status_code == 415
        oversized = client.post(
            "/documents", headers=headers, files={"file": ("x.pdf", b"%PDF-" + b"x" * 100_000)}
        )
        assert oversized.status_code == 413
        result = client.post(
            "/documents",
            headers=headers,
            files={"file": ("../../escape.pdf", b"%PDF-1.4\nvalid admission")},
        )
        assert result.status_code == 202
        assert not (tmp_path.parent.parent / "escape.pdf").exists()
