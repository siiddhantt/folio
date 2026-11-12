"""Exact scoped retrieval; stores the evidence actually offered to the answer."""

from .lifecycle import owned
from .queries import evidence


def retrieve(database, claim):
    with database.transaction() as conn:
        row = owned(conn, claim)
        if row is None:
            return None
        saved = evidence(conn, claim["id"])
        if saved:
            return saved
        matches = conn.execute(
            "SELECT ordinal,embedding <=> %s::vector AS distance FROM index_chunks "
            "WHERE index_id=%s AND embedding IS NOT NULL ORDER BY distance,ordinal LIMIT %s",
            (row["query_vector"], claim["index_id"], claim["policy"]["retrieval_chunks"]),
        ).fetchall()
        for rank, chunk in enumerate(matches, 1):
            conn.execute(
                "INSERT INTO turn_evidence VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    claim["id"],
                    claim["index_id"],
                    f"S{rank}",
                    rank,
                    chunk["ordinal"],
                    chunk["distance"],
                ),
            )
        return evidence(conn, claim["id"])
