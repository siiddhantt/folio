import psycopg
import pytest
from test_summaries import summary_document as summary_document


@pytest.mark.integration
def test_chat_document_choices_only_include_current_ready_documents_and_page(summary_document):
    settings, client, publish = summary_document
    choices = []
    for number, name in enumerate(("Old.pdf", "First.pdf", "Second.pdf", "Pending.pdf")):
        receipt, revision = publish()
        with psycopg.connect(settings.database_url) as connection:
            connection.execute(
                "UPDATE documents SET display_name=%s,created_at=%s WHERE id=%s",
                (name, f"2026-01-0{number + 1}T12:00:00Z", receipt["document_id"]),
            )
            index = connection.execute(
                "UPDATE document_indexes SET state=%s WHERE revision_id=%s RETURNING id",
                ("pending" if number == 3 else "ready", revision),
            ).fetchone()[0]
            if number == 0:
                connection.execute(
                    "UPDATE documents SET active_revision_id=NULL WHERE id=%s",
                    (receipt["document_id"],),
                )
        choices.append(
            {
                "document_id": receipt["document_id"],
                "index_id": str(index),
                "display_name": name,
                "created_at": f"2026-01-0{number + 1}T12:00:00+00:00",
            }
        )

    response = client.get("/conversation-documents?limit=1")
    assert response.status_code == 200
    assert response.json() == {"items": [choices[2]], "next_cursor": choices[2]["document_id"]}
    older = client.get(f"/conversation-documents?limit=1&before={choices[2]['document_id']}")
    assert older.json() == {"items": [choices[1]], "next_cursor": None}
    selected = client.get(f"/conversation-documents?index_id={choices[1]['index_id']}")
    assert selected.json() == {"items": [choices[1]], "next_cursor": None}
    assert client.get(f"/conversation-documents?index_id={choices[0]['index_id']}").json() == {
        "items": [],
        "next_cursor": None,
    }
    assert client.get("/conversation-documents?limit=101").status_code == 422
    assert client.get("/conversations").json()["items"] == []
