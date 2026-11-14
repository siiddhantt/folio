import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_summaries import summary_document as summary_document


@pytest.mark.integration
def test_activity_keeps_recent_index_attempts_without_exposing_provider_payloads(summary_document):
    settings, client, publish = summary_document
    receipt, revision_id = publish()
    with psycopg.connect(settings.database_url) as connection:
        index_id = connection.execute(
            """INSERT INTO document_indexes(id,revision_id,document_id,policy,state)
            VALUES (%s,%s,%s,%s,'failed') ON CONFLICT (revision_id)
            DO UPDATE SET state='failed' RETURNING id""",
            (uuid4(), revision_id, receipt["document_id"], Jsonb({})),
        ).fetchone()[0]
        attempts = [(uuid4(), index_id, number, uuid4()) for number in range(1, 52)]
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO indexing_attempts(id,index_id,attempt_no,token,state) "
                "VALUES (%s,%s,%s,%s,'failed')",
                attempts,
            )
        connection.execute(
            """INSERT INTO embedding_invocations
            (id,index_id,attempt_id,reserved_usd,billing_state,metadata)
            VALUES (%s,%s,%s,0.01,'unknown',%s)""",
            (
                uuid4(),
                index_id,
                attempts[-1][0],
                Jsonb(
                    {
                        "prompt_tokens": None,
                        "input_tokens": 12,
                        "response_id": None,
                        "input_hash": "b" * 64,
                        "chunk_ordinals": [1, 2],
                        "model": {"PRIVATE_PROVIDER_PAYLOAD": "not a model identifier"},
                        "raw": "PRIVATE_PROVIDER_PAYLOAD",
                    }
                ),
            ),
        )
    details = client.get(f"/development/ingestion-requests/{receipt['request_id']}").json()[
        "indexing"
    ]
    assert details["state"] == "failed"
    assert details["has_more"] is True
    assert [attempt["attempt_no"] for attempt in details["attempts"]] == list(range(2, 52))
    latest = details["attempts"][-1]
    assert latest["billing_state"] == "unknown"
    assert latest["cost_usd"] is None
    assert latest["reserved_usd"] == 0.01
    assert latest["usage"] == {"input_tokens": 12}
    assert latest["chunk_ordinals"] == [1, 2]
    assert "PRIVATE_PROVIDER_PAYLOAD" not in json.dumps(details)
