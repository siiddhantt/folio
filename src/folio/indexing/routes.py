from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .config import capture_policy
from .inspection import read_index
from .lifecycle import insert_intent


def create_router(database, settings):
    router = APIRouter()

    @router.get("/revisions/{revision_id}/index")
    def index(revision_id: UUID):
        value = read_index(database, revision_id)
        if value is None:
            raise HTTPException(404, "Extraction revision not found")
        return value

    @router.post("/revisions/{revision_id}/index", status_code=202)
    def start_index(revision_id: UUID):
        with database.transaction() as conn:
            revision = conn.execute(
                "SELECT document_id FROM extraction_revisions WHERE id=%s", (revision_id,)
            ).fetchone()
            if revision is None:
                raise HTTPException(404, "Extraction revision not found")
            insert_intent(conn, revision_id, revision["document_id"], capture_policy(settings))
        return read_index(database, revision_id)

    @router.get("/revisions/{revision_id}/index/chunks")
    def chunks(
        revision_id: UUID, after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
    ):
        with database.transaction() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            row = conn.execute(
                "SELECT id,state FROM document_indexes WHERE revision_id=%s", (revision_id,)
            ).fetchone()
            if row is None or row["state"] != "ready":
                raise HTTPException(409, "The complete document index is not ready")
            found = conn.execute(
                "SELECT ordinal,text,tokens FROM index_chunks "
                "WHERE index_id=%s AND ordinal>%s "
                "ORDER BY ordinal LIMIT %s",
                (row["id"], after, limit + 1),
            ).fetchall()
            page = found[:limit]
            links = conn.execute(
                """SELECT s.chunk_ordinal,s.element_id,s.role,l.page_no FROM chunk_sources s
                JOIN element_locations l
                ON l.revision_id=s.revision_id AND l.element_id=s.element_id
                WHERE s.index_id=%s AND s.chunk_ordinal=ANY(%s)
                ORDER BY s.chunk_ordinal,s.source_order,l.location_no""",
                (row["id"], [c["ordinal"] for c in page]),
            ).fetchall()
            for chunk in page:
                chunk["sources"] = [
                    {k: v for k, v in link.items() if k != "chunk_ordinal"}
                    for link in links
                    if link["chunk_ordinal"] == chunk["ordinal"]
                ]
        return {
            "index_id": row["id"],
            "revision_id": revision_id,
            "chunks": page,
            "next_after": page[-1]["ordinal"] if len(found) > limit else None,
            "source_precision": "whole_element",
        }

    return router
