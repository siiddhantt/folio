from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from folio.api import create_app
from folio.config import Settings


@pytest.mark.integration
def test_history_reopens_accepted_uploads_and_pages_past_new_arrivals(tmp_path):
    settings = Settings(_env_file=None, artifact_root=tmp_path, development_mode=False)
    original = b"%PDF-1.4\nSynthetic history input"
    with TestClient(create_app(settings)) as client:
        assert client.get("/ingestion-requests").json() == {"items": [], "next_cursor": None}
        receipts = []
        for name in ("first.pdf", "second.pdf", "third.pdf"):
            key = str(uuid4())
            response = client.post(
                "/documents",
                headers={"Idempotency-Key": key},
                files={"file": (name, original)},
            )
            receipts.append(response.json())
            replay = client.post(
                "/documents",
                headers={"Idempotency-Key": key},
                files={"file": (name, original)},
            )
            assert replay.json() == response.json()
        # Deliberately exercise the tie-breaker, not wall-clock precision.
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("UPDATE ingestion_requests SET created_at='2026-01-01T00:00:00Z'")
        first = client.get("/ingestion-requests", params={"limit": 2}).json()
        assert len(first["items"]) == 2
        assert first["next_cursor"]
        new = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("new.pdf", original)},
        ).json()

    with TestClient(create_app(settings)) as restarted:
        last = restarted.get(
            "/ingestion-requests", params={"limit": 2, "before": first["next_cursor"]}
        ).json()
        items = first["items"] + last["items"]
        assert [item["request_id"] for item in items] == sorted(
            (receipt["request_id"] for receipt in receipts), reverse=True
        )
        assert last["next_cursor"] is None
        assert (
            restarted.get("/ingestion-requests").json()["items"][0]["request_id"]
            == new["request_id"]
        )
        selected = items[0]
        assert selected["extraction_state"] == "open"
        assert selected["current_attempt_state"] == "pending"
        assert selected["revision_id"] is None
        assert selected["summary_state"] == "not_scheduled"
        assert selected["extraction_error_code"] is None
        assert selected["summary_error_code"] is None
        document = restarted.get(f"/documents/{selected['document_id']}").json()
        assert document["current_request_id"] == selected["request_id"]
        assert document["display_name"] == selected["filename"]
        assert restarted.get(f"/documents/{selected['document_id']}/original").content == original


@pytest.mark.integration
def test_history_rejects_invalid_bounds_and_cursors():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        for parameters in (
            {"limit": 0},
            {"limit": 101},
            {"before": "not-a-cursor"},
            {"before": "e30="},
            {"before": "A" * 513},
        ):
            assert client.get("/ingestion-requests", params=parameters).status_code == 422
