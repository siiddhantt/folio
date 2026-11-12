"""Exact scoped retrieval; stores the evidence actually offered to the answer."""

from .lifecycle import owned
from .queries import evidence


def retrieve(database, claim, *, defer_publication=False):
    with database.transaction() as conn:
        row = owned(conn, claim)
        if row is None:
            return None
        saved = evidence(conn, claim["id"])
        if saved:
            return saved
        matches = conn.execute(
            "WITH matches AS (SELECT ordinal,text,embedding <=> %s::vector AS distance "
            "FROM index_chunks WHERE index_id=%s AND embedding IS NOT NULL "
            "ORDER BY distance,ordinal LIMIT %s) "
            "SELECT m.ordinal AS chunk_ordinal,m.text,m.distance,"
            "array_agg(DISTINCT l.page_no ORDER BY l.page_no) AS pages "
            "FROM matches m JOIN chunk_sources s ON s.index_id=%s AND s.chunk_ordinal=m.ordinal "
            "JOIN element_locations l ON l.revision_id=s.revision_id AND l.element_id=s.element_id "
            "GROUP BY m.ordinal,m.text,m.distance ORDER BY m.distance,m.ordinal",
            (
                row["query_vector"],
                claim["index_id"],
                claim["policy"]["retrieval_chunks"],
                claim["index_id"],
            ),
        ).fetchall()
        for rank, chunk in enumerate(matches, 1):
            chunk.update(rank=rank, source_id=f"S{rank}")
        if defer_publication:
            return matches
        save_evidence(conn, claim, matches)
        return evidence(conn, claim["id"])


def save_evidence(conn, claim, passages):
    """Caller has checked ownership; save the exact whole chunks selected for input."""
    for passage in passages:
        conn.execute(
            "INSERT INTO turn_evidence VALUES (%s,%s,%s,%s,%s,%s)",
            (
                claim["id"],
                claim["index_id"],
                passage["source_id"],
                passage["rank"],
                passage["chunk_ordinal"],
                passage["distance"],
            ),
        )
