"""Freeze the original terminal prefix used as context, never as PDF evidence."""

import hashlib
import json

from psycopg.types.json import Jsonb

from folio.ai.tokens import count_tokens

from .invocations import AdmissionError
from .lifecycle import owned


def build_context(conn, turn):
    history = []
    rows = conn.execute(
        "SELECT id,sequence,question,state,result FROM conversation_turns "
        "WHERE conversation_id=%s AND sequence<=%s ORDER BY sequence",
        (turn["conversation_id"], turn["parent_sequence"]),
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
    serialized = json.dumps(history, ensure_ascii=False, sort_keys=True)
    tokens = count_tokens(serialized, turn["policy"]["model_id"])
    # Reject the entire over-limit prefix, rather than silently losing older turns.
    if tokens > turn["policy"]["history_limit_tokens"]:
        raise AdmissionError("CHAT_HISTORY_LIMIT")
    return {
        "version": 1,
        "through_sequence": turn["parent_sequence"],
        "history": history,
        "tokens": tokens,
        "sha256": hashlib.sha256(serialized.encode()).hexdigest(),
    }


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
