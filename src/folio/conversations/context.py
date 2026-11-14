"""Freeze the original terminal prefix used as context, never as PDF evidence."""

import hashlib
import json

from psycopg.types.json import Jsonb

from folio.ai.tokens import count_tokens

from .invocations import AdmissionError
from .lifecycle import owned


def terminal_history(conn, conversation_id, through_sequence, after_sequence=0):
    history = []
    rows = conn.execute(
        "SELECT id,sequence,question,state,result FROM conversation_turns "
        "WHERE conversation_id=%s AND sequence<=%s AND sequence>%s ORDER BY sequence",
        (conversation_id, through_sequence, after_sequence),
    )
    for previous in rows:
        if previous["state"] in {"pending", "running"}:
            raise AdmissionError("CHAT_CONTEXT_NOT_READY")
        result = previous["result"] or {}
        history.append(
            {
                "turn_id": str(previous["id"]),
                "sequence": previous["sequence"],
                "question": previous["question"],
                "outcome": result.get("outcome", "unanswered"),
                "answer": [statement["text"] for statement in result.get("statements", [])],
            }
        )
    return history


def latest_memory(conn, conversation_id, through_sequence):
    row = conn.execute(
        "SELECT id,covered_through,result FROM conversation_memories "
        "WHERE conversation_id=%s AND state='ready' AND covered_through<=%s "
        "ORDER BY covered_through DESC LIMIT 1",
        (conversation_id, through_sequence),
    ).fetchone()
    return (
        {"id": str(row["id"]), "covered_through": row["covered_through"], **row["result"]}
        if row
        else None
    )


def snapshot(history, through_sequence, model_id, memory=None, *, version=1):
    payload = {"memory": memory, "history": history} if version == 2 else history
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    value = {
        "version": version,
        "through_sequence": through_sequence,
        "history": history,
        "tokens": count_tokens(serialized, model_id),
        "sha256": hashlib.sha256(serialized.encode()).hexdigest(),
    }
    if version == 2:
        value["memory"] = memory
    return value


def build_context(conn, turn, *, enforce_limit=True):
    memory = (
        latest_memory(conn, turn["conversation_id"], turn["parent_sequence"])
        if "memory" in turn["policy"]
        else None
    )
    history = terminal_history(
        conn,
        turn["conversation_id"],
        turn["parent_sequence"],
        memory["covered_through"] if memory else 0,
    )
    context = snapshot(
        history,
        turn["parent_sequence"],
        turn["policy"]["model_id"],
        memory,
        version=2 if "memory" in turn["policy"] else 1,
    )
    # Reject the entire over-limit prefix, rather than silently losing older turns.
    if enforce_limit and context["tokens"] > turn["policy"]["history_limit_tokens"]:
        raise AdmissionError("CHAT_HISTORY_LIMIT")
    return context


def ensure_context(database, claim):
    with database.transaction() as conn:
        row = owned(conn, claim)
        if row is None:
            return None
        if row["context_snapshot"] is not None:
            return row["context_snapshot"]
        context = build_context(conn, row)
        conn.execute(
            "UPDATE conversation_turns SET context_snapshot=%s WHERE id=%s",
            (Jsonb(context), row["id"]),
        )
        return context
