"""Public API documentation can be inspected without opening the database."""

import pytest
from fastapi.testclient import TestClient

from folio.api import create_app
from folio.config import Settings


@pytest.fixture
def contract(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            database_url="postgresql://folio:folio@127.0.0.1:1/unused",
            artifact_root=tmp_path,
            development_mode=False,
        )
    )
    # No lifespan context: /openapi.json must not need live infrastructure.
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def resolve(contract, schema):
    if "$ref" in schema:
        return contract["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
    return schema


def test_public_json_success_responses_describe_their_fields(contract):
    missing = []
    for path, operations in contract["paths"].items():
        if path.startswith("/development/"):
            continue
        for method, operation in operations.items():
            for status, response in operation["responses"].items():
                content = response.get("content", {}).get("application/json")
                if status.startswith("2") and content is not None:
                    schema = resolve(contract, content.get("schema", {}))
                    if not schema.get("properties"):
                        missing.append(f"{method.upper()} {path} ({status})")
    assert not missing, f"Missing public response fields: {missing}"


def test_original_download_and_removal_have_their_actual_media_contracts(contract):
    original = contract["paths"]["/documents/{document_id}/original"]["get"]["responses"]["200"]
    assert set(original["content"]) == {"application/pdf"}
    assert original["content"]["application/pdf"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    removed = contract["paths"]["/conversations/{conversation_id}"]["delete"]["responses"]["204"]
    assert "content" not in removed


def test_summary_contract_preserves_absent_results_and_decimal_cost_strings(contract):
    schemas = contract["components"]["schemas"]
    summary = schemas["DocumentSummary"]["properties"]
    assert {part.get("type") for part in summary["run_id"]["anyOf"]} == {"string", "null"}
    assert {"type": "null"} in summary["overview"]["anyOf"]
    usage = resolve(contract, summary["usage"])["properties"]
    assert {part["type"] for part in usage["cost_usd"]["anyOf"]} == {"string", "null"}
    assert usage["uncertain_cost_usd"]["type"] == "string"
    assert "not_scheduled" in summary["state"]["enum"]
    assert {"run_id", "overview", "usage", "coverage", "error"} <= set(
        schemas["DocumentSummary"]["required"]
    )


def test_turn_contract_keeps_pdf_and_transcript_references_distinct(contract):
    schemas = contract["components"]["schemas"]
    turn = schemas["ConversationTurn"]["properties"]
    assert {"type": "null"} in turn["answer"]["anyOf"]
    answer = resolve(contract, next(part for part in turn["answer"]["anyOf"] if "$ref" in part))
    assert set(answer["properties"]["outcome"]["enum"]) == {
        "answer",
        "clarification",
        "insufficient_evidence",
        "transcript",
    }
    statement = resolve(contract, answer["properties"]["statements"]["items"])
    assert {"text", "source_ids"} <= set(statement["required"])
    assert "turn_ids" not in statement["required"]
    assert statement["properties"]["turn_ids"]["items"]["type"] == "string"
    citation = resolve(contract, turn["citations"]["items"])
    assert set(citation["properties"]) == {"source_id", "chunk_ordinal", "text", "pages"}
