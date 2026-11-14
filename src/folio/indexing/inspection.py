"""Persisted indexing facts without vectors, credentials or source text."""


def read_index(database, revision_id, details=False):
    with database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return _read(connection, revision_id, details)


def inspect_index(connection, request_id):
    revision = connection.execute(
        "SELECT id FROM extraction_revisions WHERE request_id=%s", (request_id,)
    ).fetchone()
    return _read(connection, revision["id"], True) if revision else None


def _read(connection, revision_id, details):
    row = connection.execute(
        """SELECT r.diagnostics,i.id AS index_id,i.state,i.policy,i.manifest,
        i.chunk_count,i.created_at,i.started_at,i.finished_at,i.error_code,
        i.available_at,i.lease_expires_at,i.dispatch_error,
        (SELECT count(*) FROM index_chunks c WHERE c.index_id=i.id
            AND c.embedding IS NOT NULL) AS embedded_chunks
        FROM extraction_revisions r LEFT JOIN document_indexes i ON i.revision_id=r.id
        WHERE r.id=%s""",
        (revision_id,),
    ).fetchone()
    if row is None:
        return None
    policy, manifest = row.pop("policy") or {}, row.pop("manifest") or {}
    diagnostics = row.pop("diagnostics")
    result = row | {
        "state": row["state"] or "not_started",
        "chunk_count": row["chunk_count"] or 0,
        "model_id": policy.get("model_id"),
        "dimensions": policy.get("dimensions"),
        "coverage": {
            "diagnostics": diagnostics,
            "pages_without_content": [
                page["page_no"]
                for page in connection.execute(
                    "SELECT page_no FROM source_pages WHERE revision_id=%s "
                    "AND content_observation='no_content_recovered' ORDER BY page_no",
                    (revision_id,),
                ).fetchall()
            ],
        },
        "exclusions": manifest.get("exclusions", []),
        "warnings": manifest.get("warnings", []),
    }
    if not details:
        return result
    attempts = connection.execute(
        """SELECT a.id,a.attempt_no,a.batch_no,a.state,a.started_at,a.finished_at,
        a.error_code,a.failure_diagnostics,v.invoked_at,v.reserved_usd,v.cost_usd,
        COALESCE(v.billing_state,'none') AS billing_state,v.metadata
        FROM indexing_attempts a LEFT JOIN embedding_invocations v ON v.attempt_id=a.id
        WHERE a.index_id=%s ORDER BY a.attempt_no DESC LIMIT 51""",
        (row["index_id"],),
    ).fetchall()
    result["has_more"] = len(attempts) > 50
    result["attempts"] = list(reversed(attempts[:50]))
    for attempt in result["attempts"]:
        metadata = attempt.pop("metadata") or {}
        attempt["usage"] = {
            key: metadata[key]
            for key in ("prompt_tokens", "input_tokens")
            if type(metadata.get(key)) is int and metadata[key] >= 0
        } | {
            key: metadata[key]
            for key in ("model", "requested_provider")
            if isinstance(metadata.get(key), str)
        }
        for key in ("response_id", "input_hash"):
            attempt[key] = metadata.get(key) if isinstance(metadata.get(key), str) else None
        ordinals = metadata.get("chunk_ordinals", [])
        attempt["chunk_ordinals"] = (
            ordinals
            if isinstance(ordinals, list) and all(type(n) is int and n > 0 for n in ordinals)
            else []
        )
    return result
