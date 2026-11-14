import json

import psycopg
import pytest
from psycopg.rows import dict_row
from test_conversations import chat_document as chat_document
from test_summaries import summary_document as summary_document

from folio.conversations.retrieval import vector_candidates


@pytest.fixture
def indexed_passages(chat_document):
    settings, _, indexes = chat_document
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        revision = conn.execute(
            "SELECT revision_id FROM document_indexes WHERE id=%s", (indexes[0],)
        ).fetchone()["revision_id"]
        for ordinal in range(2, 16):
            conn.execute(
                "INSERT INTO index_chunks "
                "(index_id,revision_id,ordinal,batch_no,text,tokens,sha256,embedding) "
                "VALUES (%s,%s,%s,1,%s,12,%s,%s::vector)",
                (
                    indexes[0],
                    revision,
                    ordinal,
                    "RX-24 homeowner's policy: 48-hour repair exception"
                    if ordinal == 14
                    else "Ordinary renewal terms.",
                    "b" * 64,
                    json.dumps([1, (ordinal // 2) / 20] + [0] * 1534) if ordinal < 15 else None,
                ),
            )
            conn.execute(
                "INSERT INTO chunk_sources VALUES (%s,%s,%s,0,'first','body')",
                (indexes[0], revision, ordinal),
            )
        conn.execute(
            "UPDATE index_chunks SET text='RX-24 OTHER_DOCUMENT_SENTINEL' WHERE index_id=%s",
            (indexes[1],),
        )
    return settings.database_url, indexes[0], json.dumps([1] + [0] * 1535)


@pytest.mark.integration
def test_vector_selection_is_scoped_ordered_and_preserves_sources(indexed_passages):
    url, index, vector = indexed_passages
    with psycopg.connect(url, row_factory=dict_row) as conn:
        six = vector_candidates(conn, index, vector, 6)
        twelve = vector_candidates(conn, index, vector, 12)
        all_embedded = vector_candidates(conn, index, vector, 20)
    assert [row["chunk_ordinal"] for row in six] == [1, 2, 3, 4, 5, 6]
    assert [row["chunk_ordinal"] for row in twelve] == list(range(1, 13))
    assert twelve[:6] == six
    assert all(row["pages"] == [1] for row in twelve)
    assert [row["source_id"] for row in six] == ["S1", "S2", "S3", "S4", "S5", "S6"]
    assert all("OTHER_DOCUMENT" not in row["text"] for row in twelve)
    assert [row["chunk_ordinal"] for row in all_embedded] == list(range(1, 15))


@pytest.mark.integration
@pytest.mark.parametrize(
    "question", ["RX-24", 'What are the policies for "RX-24" or 48-hour repairs?']
)
def test_keyword_branch_recovers_scoped_exception_outside_vector_pool(indexed_passages, question):
    from notebooks.retrieval import hybrid_candidates

    url, index, vector = indexed_passages
    with psycopg.connect(url, row_factory=dict_row) as conn:
        selected, diagnostic = hybrid_candidates(conn, index, vector, question)
    assert [row["chunk_ordinal"] for row in selected] == [1, 14, 2, 3, 4, 5]
    assert [row["chunk_ordinal"] for row in diagnostic["lexical"]] == [14]
    assert selected[1]["pages"] == [1]
    assert selected[1]["source_id"] == "S2"
    assert selected[1]["distance"] > selected[2]["distance"]
    assert "OTHER_DOCUMENT" not in json.dumps(selected)
    assert [row["source_id"] for row in diagnostic["vector"]] == [f"S{i}" for i in range(1, 13)]


@pytest.mark.integration
@pytest.mark.parametrize("question,status", [("the and of", "empty"), ("qzzzx", "no_matches")])
def test_empty_keyword_branch_preserves_vector_results(indexed_passages, question, status):
    from notebooks.retrieval import hybrid_candidates

    url, index, vector = indexed_passages
    with psycopg.connect(url, row_factory=dict_row) as conn:
        expected = vector_candidates(conn, index, vector, 6)
        selected, diagnostic = hybrid_candidates(conn, index, vector, question)
    assert selected == expected
    assert diagnostic["lexical_status"] == status


@pytest.mark.integration
def test_hybrid_rewards_branch_agreement_without_duplicate_chunks(indexed_passages):
    from notebooks.retrieval import hybrid_candidates

    url, index, vector = indexed_passages
    with psycopg.connect(url, row_factory=dict_row) as conn:
        selected, diagnostic = hybrid_candidates(conn, index, vector, "renewal")
    assert [row["chunk_ordinal"] for row in selected] == [2, 3, 4, 5, 6, 7]
    assert len(diagnostic["pool"]) == 13
    assert len({row["chunk_ordinal"] for row in diagnostic["pool"]}) == 13
    assert selected[0]["vector_rank"] == 2 and selected[0]["lexical_rank"] == 1
