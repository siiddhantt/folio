"""Prepare context before a worker claim; waiting consumes no attempt or worker slot."""

import json

from psycopg.types.json import Jsonb

from folio.ai.tokens import BudgetError, count_tokens
from folio.conversations.context import build_context, snapshot
from folio.conversations.invocations import AdmissionError
from folio.conversations.lifecycle import lock_conversation, transition
from folio.conversations.preparation import prepare
from folio.conversations.resolver import prepare_resolution
from folio.observability import log_event

from .planning import plan


def fits(turn, context):
    policy = turn["policy"]
    if context["tokens"] > policy["history_limit_tokens"]:
        return False
    messages, schema = prepare(
        turn["question"],
        [],
        {},
        include_title=turn["sequence"] == 1,
        history=context["history"],
        memory=context.get("memory"),
    )
    stages = [(messages, schema, policy["model_id"], policy["input_limit_tokens"])]
    if turn["parent_sequence"]:
        messages, schema = prepare_resolution(
            turn["question"],
            context["history"],
            prompt_version=policy.get("rewrite_prompt_version", 1),
            memory=context.get("memory"),
        )
        stages.append(
            (messages, schema, policy["rewrite_model_id"], policy["rewrite_input_limit_tokens"])
        )
    return all(
        count_tokens(
            json.dumps({"messages": messages, "schema": schema}, ensure_ascii=False), model
        )
        + policy["token_margin"]
        <= limit
        for messages, schema, model, limit in stages
    )


def prepare_pending(database, turn_id):
    try:
        return _prepare_pending(database, turn_id)
    except (BudgetError, AdmissionError) as error:
        code = error.code.replace("SUMMARY_", "CHAT_", 1)
        with database.transaction() as conn:
            identity = conn.execute(
                "SELECT conversation_id FROM conversation_turns WHERE id=%s", (turn_id,)
            ).fetchone()
            if identity is None or lock_conversation(conn, identity["conversation_id"]) is None:
                return None
            turn = conn.execute(
                "SELECT * FROM conversation_turns WHERE id=%s AND state='pending' FOR UPDATE",
                (turn_id,),
            ).fetchone()
            if turn is None or turn["context_snapshot"] is not None:
                return None
            transition(conn, turn, code=code, unavailable=True)
            conn.execute(
                "UPDATE conversation_turns SET memory_check_needed=false WHERE id=%s", (turn_id,)
            )
        log_event("chat_context_unavailable", turn_id=str(turn_id), error_code=code, error=error)
        return {"outcome": "unavailable", "code": code}


def _prepare_pending(database, turn_id):
    with database.transaction() as conn:
        identity = conn.execute(
            "SELECT conversation_id FROM conversation_turns WHERE id=%s", (turn_id,)
        ).fetchone()
        if identity is None or lock_conversation(conn, identity["conversation_id"]) is None:
            return None
        turn = conn.execute(
            "SELECT * FROM conversation_turns WHERE id=%s AND state='pending' FOR UPDATE",
            (turn_id,),
        ).fetchone()
        if turn is None or turn["context_snapshot"] is not None or "memory" not in turn["policy"]:
            return None
        if (
            turn["context_deadline"] is not None
            and turn["context_deadline"]
            <= conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        ):
            transition(conn, turn, code="CHAT_CONTEXT_WAIT_EXPIRED", unavailable=True)
            return {"outcome": "unavailable", "code": "CHAT_CONTEXT_WAIT_EXPIRED"}
        context = build_context(conn, turn, enforce_limit=False)
        if fits(turn, context):
            conn.execute(
                "UPDATE conversation_turns SET context_snapshot=%s,context_deadline=NULL WHERE "
                "id=%s",
                (Jsonb(context), turn_id),
            )
            return None
        code = None
        empty = snapshot([], turn["parent_sequence"], turn["policy"]["model_id"], version=2)
        if not fits(turn, empty):
            code = "CHAT_INPUT_LIMIT"
        recent = snapshot(
            context["history"][-turn["policy"]["memory"]["keep_turns"] :],
            turn["parent_sequence"],
            turn["policy"]["model_id"],
            version=2,
        )
        if code is None and not fits(turn, recent):
            code = "CHAT_HISTORY_LIMIT"
        dependency = None
        if turn["memory_dependency_id"]:
            dependency = conn.execute(
                "SELECT * FROM conversation_memories WHERE id=%s FOR UPDATE",
                (turn["memory_dependency_id"],),
            ).fetchone()
            if dependency["state"] == "ready":
                code = "CHAT_HISTORY_LIMIT"
            elif dependency["state"] in {"failed", "unavailable"}:
                code = "CHAT_CONTEXT_PREPARATION_FAILED"
        if code is None and dependency is None:
            dependency = plan(
                conn,
                turn["conversation_id"],
                turn["index_id"],
                turn["parent_sequence"],
                turn["policy"],
                foreground=True,
            )
            if dependency is None:
                code = "CHAT_HISTORY_LIMIT"
            elif dependency["state"] in {"failed", "unavailable"}:
                code = "CHAT_CONTEXT_PREPARATION_FAILED"
        if code:
            transition(conn, turn, code=code, unavailable=True)
            return {"outcome": "unavailable", "code": code}
        conn.execute(
            "UPDATE conversation_memories SET "
            "foreground=true,deferred_reason=NULL,next_dispatch_at=clock_timestamp() "
            "WHERE id=%s AND state='pending'",
            (dependency["id"],),
        )
        conn.execute(
            "UPDATE conversation_turns SET "
            "memory_dependency_id=%s,context_deadline=COALESCE(context_deadline,"
            "clock_timestamp()+%s*interval '1 second'),transport_job_id=NULL WHERE id=%s",
            (dependency["id"], turn["policy"]["memory"]["wait_seconds"], turn_id),
        )
        return {"outcome": "pending"}


def prepare_batch(database, limit=20, turn_id=None):
    with database.transaction() as conn:
        rows = conn.execute(
            "SELECT t.id FROM conversation_turns t LEFT JOIN conversation_memories m "
            "ON m.id=t.memory_dependency_id "
            "WHERE t.state='pending' AND t.context_snapshot IS NULL AND t.policy ? 'memory' "
            "AND (t.memory_dependency_id IS NULL OR t.context_deadline<=clock_timestamp() "
            "OR m.state NOT IN ('pending','running')) "
            "AND (%s::uuid IS NULL OR t.id=%s) ORDER BY t.created_at,t.id LIMIT %s",
            (turn_id, turn_id, limit),
        ).fetchall()
    for row in rows:
        prepare_pending(database, row["id"])
