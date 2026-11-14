"""Read-only retrieval experiment; not a production routing option."""

from folio.conversations.retrieval import vector_candidates


def hybrid_candidates(conn, index_id, query_vector, question):
    """Fuse two scoped pools of twelve into six passages; keep component ranks."""
    vector = vector_candidates(conn, index_id, query_vector, 12)
    query = conn.execute(
        "SELECT coalesce(string_agg(array_to_tsvector(ARRAY[lexeme])::text, "
        "' | ' ORDER BY lexeme),'') AS query FROM "
        "unnest(tsvector_to_array(to_tsvector('pg_catalog.english',%s))) AS terms(lexeme)",
        (question,),
    ).fetchone()["query"]
    lexical = []
    if query:
        lexical = conn.execute(
            "WITH matches AS (SELECT ordinal,text,embedding <=> %s::vector AS distance,"
            "ts_rank_cd(to_tsvector('pg_catalog.english',text),%s::tsquery) AS lexical_score "
            "FROM index_chunks WHERE index_id=%s AND embedding IS NOT NULL "
            "AND to_tsvector('pg_catalog.english',text) @@ %s::tsquery "
            "ORDER BY lexical_score DESC,ordinal LIMIT 12) "
            "SELECT m.ordinal AS chunk_ordinal,m.text,m.distance,m.lexical_score,"
            "array_agg(DISTINCT l.page_no ORDER BY l.page_no) AS pages "
            "FROM matches m JOIN chunk_sources s ON s.index_id=%s AND s.chunk_ordinal=m.ordinal "
            "JOIN element_locations l ON l.revision_id=s.revision_id AND l.element_id=s.element_id "
            "GROUP BY m.ordinal,m.text,m.distance,m.lexical_score "
            "ORDER BY m.lexical_score DESC,m.ordinal",
            (query_vector, query, index_id, query, index_id),
        ).fetchall()
    diagnostic = {
        "lexical_query": query,
        "lexical_status": "matched" if lexical else "no_matches" if query else "empty",
        "vector": vector,
        "lexical": lexical,
    }
    if not lexical:
        return vector[:6], diagnostic | {"pool": vector}
    pool = {}
    for branch, rows in (("vector", vector), ("lexical", lexical)):
        for rank, row in enumerate(rows, 1):
            item = pool.setdefault(
                row["chunk_ordinal"], row | {"vector_rank": None, "lexical_rank": None, "rrf": 0}
            )
            item[f"{branch}_rank"] = rank
            item["rrf"] += 1 / (60 + rank)
    fused = sorted(pool.values(), key=lambda row: (-row["rrf"], row["chunk_ordinal"]))
    selected = [
        row | {"rank": rank, "source_id": f"S{rank}"} for rank, row in enumerate(fused[:6], 1)
    ]
    return selected, diagnostic | {"pool": fused}
