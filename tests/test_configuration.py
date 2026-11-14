from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from folio.api import create_app
from folio.config import Settings

HEADERS = {"X-Folio-Development": "1", "Origin": "http://localhost:3000"}


@pytest.mark.integration
def test_console_saves_validated_settings_and_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_SUMMARY_ENABLED", "false")
    settings = Settings(artifact_root=tmp_path, development_mode=True)
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        response = client.get("/development/settings")
        assert response.status_code == 200
        original = response.json()
        values = {**original["values"], "max_pages": 700, "max_upload_bytes": 1048576}
        saved = client.put(
            "/development/settings",
            json={"revision": original["revision"], "values": values},
            headers=HEADERS,
        )
        assert saved.status_code == 200
        assert saved.json()["values"] == values
        assert saved.json()["revision"] > original["revision"]
        assert client.get("/capabilities").json()["max_pages"] == 700
        assert (
            client.put(
                "/development/settings",
                json={"revision": original["revision"], "values": original["values"]},
                headers=HEADERS,
            ).status_code
            == 409
        )
        invalid = {**values, "parser_timeout_seconds": settings.job_timeout_seconds}
        assert (
            client.put(
                "/development/settings",
                json={"revision": saved.json()["revision"], "values": invalid},
                headers=HEADERS,
            ).status_code
            == 422
        )
    with TestClient(create_app(settings), base_url="http://localhost") as restarted:
        assert restarted.get("/development/settings").json()["values"] == values
        assert restarted.get("/capabilities").json()["max_upload_bytes"] == 1048576


@pytest.mark.integration
def test_new_uploads_freeze_settings_through_processing_and_summary(tmp_path, monkeypatch):
    from folio.ingestion.parsing.evidence import Element, Extraction, Location, Page
    from folio.ingestion.processing import process_attempt

    monkeypatch.setenv("FOLIO_SUMMARY_ENABLED", "false")
    settings = Settings(artifact_root=tmp_path, development_mode=True)
    original = b"%PDF-1.4\nA controlled document"
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        before = client.get("/development/settings").json()
        key = str(uuid4())

        def upload(key):
            response = client.post(
                "/documents",
                headers={"Idempotency-Key": key},
                files={"file": ("report.pdf", original)},
            )
            assert response.status_code == 202
            return response.json()

        first = upload(key)
        updated = client.put(
            "/development/settings",
            headers=HEADERS,
            json={
                "revision": before["revision"],
                "values": {
                    **before["values"],
                    "max_pages": 700,
                    "summary_enabled": True,
                    "summary_max_output_tokens": 8192,
                    "max_upload_bytes": 64,
                },
            },
        ).json()
        assert upload(key) == first
        second = upload(str(uuid4()))

        for receipt, pages, enabled, revision in [
            (first, 100, False, before["revision"]),
            (second, 700, True, updated["revision"]),
        ]:
            details = client.get(f"/development/ingestion-requests/{receipt['request_id']}").json()
            assert details["configuration"]["settings_revision"] == revision
            assert details["configuration"]["max_pages"] == pages
            assert details["summary_configuration"]["enabled"] is enabled

            def parser(path, config, expected_pages=pages):
                assert config["max_pages"] == expected_pages
                return Extraction(
                    [Page(1, 100, 100, "content_recovered")],
                    [
                        Element(
                            "e1",
                            "paragraph",
                            0,
                            None,
                            "Revenue increased.",
                            None,
                            None,
                            [Location(1)],
                        )
                    ],
                    [],
                    "success",
                    {"fixture": True},
                    {},
                    0.1,
                )

            status = client.get(receipt["status_url"]).json()
            result = process_attempt(
                receipt["request_id"],
                status["authorized_attempt_id"],
                settings=settings,
                parser=parser,
            )
            summary = client.get(f"/revisions/{result['revision_id']}/summary").json()
            assert summary["state"] == ("pending" if enabled else "unavailable")
            if not enabled:
                assert summary["error"]["code"] == "SUMMARY_DISABLED"

        for length in [65, 70000]:
            rejected = client.post(
                "/documents",
                headers={"Idempotency-Key": str(uuid4())},
                files={"file": ("big.pdf", b"%PDF-1.4\n" + b"x" * length)},
            )
            assert rejected.status_code == 413


@pytest.mark.integration
def test_lowering_upload_limit_keeps_existing_idempotent_receipts_recoverable(tmp_path):
    settings = Settings(artifact_root=tmp_path, development_mode=True)
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        key = str(uuid4())
        original = b"%PDF-1.4\n" + b"a" * 100

        def upload(key, content):
            return client.post(
                "/documents",
                headers={"Idempotency-Key": key},
                files={"file": ("report.pdf", content)},
            )

        receipt = upload(key, original).json()
        current = client.get("/development/settings").json()
        response = client.put(
            "/development/settings",
            headers=HEADERS,
            json={
                "revision": current["revision"],
                "values": {**current["values"], "max_upload_bytes": 32},
            },
        )
        assert response.status_code == 200
        assert upload(key, original).json() == receipt
        assert upload(str(uuid4()), original).status_code == 413
        assert upload(key, original[:-1] + b"b").status_code == 409


@pytest.mark.integration
def test_console_is_local_explicit_and_cannot_change_spending_limits(tmp_path):
    settings = Settings(artifact_root=tmp_path, development_mode=True)
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        current = client.get("/development/settings").json()
        payload = {"revision": current["revision"], "values": current["values"]}
        assert (
            client.get("/development/settings", headers={"Host": "example.com"}).status_code == 403
        )
        for origin in ["https://example.com", "null", "http://[", "http://localhost:wrong"]:
            assert (
                client.get("/development/settings", headers={"Origin": origin}).status_code == 403
            )
        assert client.put("/development/settings", json=payload).status_code == 403
        for extra in [{"budget_usd": "20"}, {"api_key": "not-a-secret"}, {"max_pages": 0}]:
            invalid = {**payload, "values": {**current["values"], **extra}}
            assert (
                client.put("/development/settings", json=invalid, headers=HEADERS).status_code
                == 422
            )
        unchanged = client.get("/development/settings").json()
        assert unchanged == current
        saved = client.put(
            "/development/settings",
            headers=HEADERS,
            json={
                **payload,
                "values": {**current["values"], "max_pages": 321},
            },
        )
        assert saved.status_code == 200
        assert saved.json()["runtime"] == current["runtime"]
    settings.development_mode = False
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        assert client.get("/development/settings").status_code == 404
        assert client.put("/development/settings", json=payload, headers=HEADERS).status_code == 404
        assert client.get("/capabilities").json()["max_pages"] == 321


@pytest.mark.integration
def test_known_summary_execution_mismatch_cannot_be_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_SUMMARY_ENABLED", "false")
    monkeypatch.setenv("FOLIO_SUMMARY_TIMEOUT_SECONDS", "90")
    settings = Settings(
        artifact_root=tmp_path,
        development_mode=True,
        parser_timeout_seconds=100,
        job_timeout_seconds=120,
    )
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        current = client.get("/development/settings").json()
        response = client.put(
            "/development/settings",
            headers=HEADERS,
            json={
                "revision": current["revision"],
                "values": {**current["values"], "summary_enabled": True},
            },
        )
        assert response.status_code == 422
        assert (
            current["runtime"]["summary_configuration_error"] == "SUMMARY_EXECUTION_CONFIG_MISMATCH"
        )
        assert (
            client.put(
                "/development/settings",
                headers=HEADERS,
                json={
                    "revision": current["revision"],
                    "values": current["values"],
                },
            ).status_code
            == 200
        )


@pytest.mark.integration
def test_unsupported_environment_reasoning_does_not_block_document_acceptance(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("FOLIO_SUMMARY_REASONING_EFFORT", "unsupported")
    settings = Settings(artifact_root=tmp_path, development_mode=True)
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        response = client.post(
            "/documents",
            headers={"Idempotency-Key": str(uuid4())},
            files={"file": ("report.pdf", b"%PDF-1.4\nReadable evidence")},
        )
        assert response.status_code == 202
        current = client.get("/development/settings").json()
        assert (
            client.put(
                "/development/settings",
                headers=HEADERS,
                json={
                    "revision": current["revision"],
                    "values": current["values"],
                },
            ).status_code
            == 422
        )
