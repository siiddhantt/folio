import hashlib
import json

from folio.storage import Artifacts

from .chunking import ChunkingError, prepare_chunks


def prepare(database, claim, artifact_root):
    with database.transaction() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        revision = conn.execute(
            "SELECT * FROM extraction_revisions WHERE id=%s", (claim["revision_id"],)
        ).fetchone()
        sources = conn.execute(
            """SELECT e.element_id,e.provider_ref,
            coalesce(jsonb_agg(jsonb_build_object('page_no',l.page_no)
            ORDER BY l.location_no) FILTER (WHERE l.page_no IS NOT NULL),'[]') AS locations
            FROM source_elements e LEFT JOIN element_locations l
            ON l.revision_id=e.revision_id AND l.element_id=e.element_id
            WHERE e.revision_id=%s GROUP BY e.revision_id,e.element_id ORDER BY e.reading_order""",
            (claim["revision_id"],),
        ).fetchall()
    raw = Artifacts(artifact_root).path(revision["raw_storage_key"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != revision["raw_sha256"]:
        raise ChunkingError("INDEX_SOURCE_CHANGED", "Saved extraction failed its integrity check.")
    plan = prepare_chunks(json.loads(raw), sources, token_limit=claim["policy"]["chunk_tokens"])
    if not plan["chunks"] or len(plan["chunks"]) > claim["policy"]["max_chunks"]:
        raise ChunkingError("INDEX_CHUNK_LIMIT", "The chunk plan exceeds the configured limit.")
    plan["extraction_diagnostics"] = revision["diagnostics"]
    plan["raw_sha256"] = revision["raw_sha256"]
    return plan
