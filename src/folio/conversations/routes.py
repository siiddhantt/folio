from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, Query, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .catalog import create_router as create_catalog_router
from .config import ChatSettings
from .inspection import inspect_turn
from .lifecycle import lock_conversation
from .queries import conversation, turn
from .titles import normalized_title


class NewConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index_id: UUID


class NewQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)


class RenameConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=60)
    expected_version: int = Field(ge=0, strict=True)

    @field_validator("title", mode="before")
    @classmethod
    def valid_title(cls, value):
        title = normalized_title(value)
        if title is None:
            # Reject unencodable input before validation errors echo it in JSON.
            raise HTTPException(422, "Enter a valid title of 1–60 characters.")
        return title


def create_router(database, settings):
    router = APIRouter()
    router.include_router(create_catalog_router(database))

    if settings.development_mode:

        @router.get("/development/conversation-turns/{turn_id}")
        def inspection(turn_id: UUID):
            value = inspect_turn(database, turn_id)
            if value is None:
                raise HTTPException(404, "Question not found.")
            return value

    @router.post("/conversations", status_code=201)
    def create(body: NewConversation, idempotency_key: str = Header(min_length=1, max_length=200)):
        with database.transaction() as conn:
            index = conn.execute(
                "SELECT id FROM document_indexes WHERE id=%s AND state='ready'", (body.index_id,)
            ).fetchone()
            if index is None:
                raise HTTPException(409, "This document's index is not ready.")
            conn.execute(
                "INSERT INTO conversations(id,index_id,creation_key) VALUES (%s,%s,%s) ON"
                " CONFLICT(creation_key) DO NOTHING",
                (uuid4(), body.index_id, idempotency_key),
            )
            saved = conn.execute(
                "SELECT id,index_id,deleted_at FROM conversations WHERE creation_key=%s FOR UPDATE",
                (idempotency_key,),
            ).fetchone()
            if saved["index_id"] != body.index_id:
                raise HTTPException(409, "This submission key belongs to another document.")
            if saved["deleted_at"] is not None:
                raise HTTPException(410, "This chat was deleted. Start a new chat.")
            return conversation(conn, saved["id"])

    @router.get("/conversations")
    def listing(before: UUID | None = None, limit: int = Query(20, ge=1, le=100)):
        with database.transaction() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            if (
                before
                and not conn.execute(
                    "SELECT id FROM conversations WHERE id=%s", (before,)
                ).fetchone()
            ):
                raise HTTPException(404, "Conversation cursor not found.")
            rows = conn.execute(
                "SELECT id FROM conversations WHERE deleted_at IS NULL AND "
                "(%s::uuid IS NULL OR (created_at,id)<"
                "(SELECT created_at,id FROM conversations WHERE id=%s)) ORDER BY "
                "created_at DESC,id DESC LIMIT %s",
                (before, before, limit + 1),
            ).fetchall()
            return {
                "items": [conversation(conn, r["id"]) for r in rows[:limit]],
                "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
            }

    @router.get("/conversations/{conversation_id}")
    def detail(conversation_id: UUID):
        with database.transaction() as conn:
            value = conversation(conn, conversation_id)
            if value is None:
                raise HTTPException(404, "Conversation not found.")
            return value

    @router.patch("/conversations/{conversation_id}")
    def rename(conversation_id: UUID, body: RenameConversation):
        with database.transaction() as conn:
            chat = lock_conversation(conn, conversation_id)
            if chat is None:
                raise HTTPException(404, "Conversation not found.")
            if chat["title_version"] != body.expected_version:
                raise HTTPException(
                    409, "This title changed in another tab. Review it and try again."
                )
            conn.execute(
                "UPDATE conversations SET title=%s,title_source='manual',"
                "title_version=title_version+1 WHERE id=%s",
                (body.title, conversation_id),
            )
            return conversation(conn, conversation_id)

    @router.delete("/conversations/{conversation_id}", status_code=204)
    def delete(conversation_id: UUID):
        with database.transaction() as conn:
            chat = conn.execute(
                "SELECT deleted_at FROM conversations WHERE id=%s FOR UPDATE", (conversation_id,)
            ).fetchone()
            if chat is None:
                raise HTTPException(404, "Conversation not found.")
            if chat["deleted_at"] is None:
                conn.execute(
                    "UPDATE conversations SET deleted_at=clock_timestamp() WHERE id=%s",
                    (conversation_id,),
                )
                cancelled = conn.execute(
                    "UPDATE conversation_turns SET state='unavailable',error_code='CHAT_DELETED',"
                    "claim_token=NULL,lease_expires_at=NULL,transport_job_id=NULL,"
                    "finished_at=clock_timestamp() WHERE conversation_id=%s AND "
                    "state IN ('pending','running') RETURNING id",
                    (conversation_id,),
                ).fetchall()
                for row in cancelled:
                    conn.execute(
                        "UPDATE turn_attempts SET finished_at=clock_timestamp(),"
                        "error_code='CHAT_DELETED' WHERE turn_id=%s AND finished_at IS NULL",
                        (row["id"],),
                    )
        return Response(status_code=204)

    @router.post("/conversations/{conversation_id}/turns", status_code=202)
    def submit(
        conversation_id: UUID,
        body: NewQuestion,
        idempotency_key: str = Header(min_length=1, max_length=200),
    ):
        question = body.question.strip()
        if not question:
            raise HTTPException(422, "Enter a question.")
        with database.transaction() as conn:
            chat = lock_conversation(conn, conversation_id)
            if chat is None:
                raise HTTPException(404, "Conversation not found.")
            previous = conn.execute(
                "SELECT id,question FROM conversation_turns WHERE conversation_id=%s AND "
                "idempotency_key=%s",
                (conversation_id, idempotency_key),
            ).fetchone()
            if previous:
                if previous["question"] != question:
                    raise HTTPException(409, "This submission key belongs to another question.")
                return turn(conn, previous["id"])
            if conn.execute(
                "SELECT 1 FROM conversation_turns WHERE conversation_id=%s", (conversation_id,)
            ).fetchone():
                raise HTTPException(
                    409,
                    "This version supports one question per chat. Start a new chat for "
                    "another question.",
                )
            policy = ChatSettings().policy(settings)
            turn_id = uuid4()
            conn.execute(
                "INSERT INTO conversation_turns "
                "(id,conversation_id,index_id,sequence,idempotency_key,question,policy) "
                "VALUES (%s,%s,%s,1,%s,%s,%s)",
                (
                    turn_id,
                    conversation_id,
                    chat["index_id"],
                    idempotency_key,
                    question,
                    Jsonb(policy),
                ),
            )
            saved = turn(conn, turn_id)
        from .dispatcher import dispatch_once

        dispatch_once(settings, turn_id=turn_id)
        return saved

    @router.get("/conversations/{conversation_id}/turns")
    def history(
        conversation_id: UUID, after: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
    ):
        with database.transaction() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            if conversation(conn, conversation_id) is None:
                raise HTTPException(404, "Conversation not found.")
            rows = conn.execute(
                "SELECT id,sequence FROM conversation_turns WHERE conversation_id=%s AND "
                "sequence>%s ORDER BY sequence LIMIT %s",
                (conversation_id, after, limit + 1),
            ).fetchall()
            return {
                "items": [turn(conn, r["id"]) for r in rows[:limit]],
                "next_after": rows[limit - 1]["sequence"] if len(rows) > limit else None,
            }

    @router.get("/conversations/{conversation_id}/turns/{turn_id}")
    def poll(conversation_id: UUID, turn_id: UUID):
        with database.transaction() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            value = turn(conn, turn_id)
            if value is None or value["conversation_id"] != conversation_id:
                raise HTTPException(404, "Question not found.")
            return value

    return router
