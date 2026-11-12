from uuid import UUID

from fastapi import APIRouter, HTTPException, Query


def create_router(database):
    router = APIRouter()

    @router.get("/conversation-documents")
    def listing(
        before: UUID | None = None,
        index_id: UUID | None = None,
        limit: int = Query(20, ge=1, le=100),
    ):
        with database.transaction() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            if (
                before
                and not connection.execute(
                    "SELECT 1 FROM documents WHERE id=%s", (before,)
                ).fetchone()
            ):
                raise HTTPException(404, "Document cursor not found.")
            rows = connection.execute(
                """SELECT d.id AS document_id,i.id AS index_id,d.display_name,d.created_at
                FROM documents d JOIN document_indexes i
                  ON i.document_id=d.id AND i.revision_id=d.active_revision_id
                WHERE i.state='ready' AND (%s::uuid IS NULL OR i.id=%s)
                AND (%s::uuid IS NULL OR (d.created_at,d.id)<
                  (SELECT created_at,id FROM documents WHERE id=%s))
                ORDER BY d.created_at DESC,d.id DESC LIMIT %s""",
                (index_id, index_id, before, before, limit + 1),
            ).fetchall()
        return {
            "items": rows[:limit],
            "next_cursor": rows[limit - 1]["document_id"] if len(rows) > limit else None,
        }

    return router
