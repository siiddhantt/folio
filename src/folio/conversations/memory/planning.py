"""Capture a complete old prefix after a durable terminal turn; never delete history."""

import hashlib
import json
from uuid import uuid4

from psycopg.types.json import Jsonb

from folio.ai.tokens import BudgetError, count_tokens
from folio.conversations.context import latest_memory, snapshot, terminal_history
from folio.conversations.invocations import AdmissionError
from folio.conversations.lifecycle import lock_conversation
from folio.observability import log_event

from .preparation import prepare


def plan(conn, conversation_id, index_id, through_sequence, chat_policy, *, foreground=False):
    """Caller holds the conversation lock. Reuse active/failed prefix identities."""
    active = conn.execute(
        "SELECT * FROM conversation_memories WHERE conversation_id=%s AND state IN "
        "('pending','running')",
        (conversation_id,),
    ).fetchone()
    if active:
        return active
    memory = latest_memory(conn, conversation_id, through_sequence)
    history = terminal_history(
        conn, conversation_id, through_sequence, memory["covered_through"] if memory else 0
    )
    config = chat_policy["memory"]
    current = snapshot(history, through_sequence, chat_policy["model_id"], memory, version=2)
    if not foreground and current["tokens"] < config["trigger_tokens"]:
        return None
    eligible = history[: -config["keep_turns"]]
    if not eligible:
        return None
    inherited = {
        key: chat_policy[key]
        for key in (
            "base_url",
            "reservation_version",
            "token_margin",
            "budget_usd",
            "document_budget_usd",
            "job_timeout_seconds",
            "lease_seconds",
            "max_attempts",
            "retry_delays_seconds",
        )
    }
    policy = inherited | config | {"foreground_policy": chat_policy}
    # Keep whole exchanges; reduce the selected old prefix only to fit the compactor itself.
    while eligible:
        retained_tokens = snapshot(
            history[len(eligible) :], through_sequence, chat_policy["model_id"], version=2
        )["tokens"]
        policy["notes_target_tokens"] = min(
            max(1, config["max_output_tokens"] // 2),
            max(128, config["target_tokens"] - retained_tokens),
        )
        source = {"memory": memory, "history": eligible}
        messages, schema = prepare(source, policy["notes_target_tokens"])
        tokens = count_tokens(
            json.dumps({"messages": messages, "schema": schema}, ensure_ascii=False),
            policy["model_id"],
        )
        if tokens + policy["token_margin"] <= policy["input_limit_tokens"]:
            break
        eligible = eligible[:-1]
    if not eligible:
        return None
    serialized = json.dumps(source, ensure_ascii=False, sort_keys=True)
    predecessor = memory["id"] if memory else None
    covered = eligible[-1]["sequence"]
    conn.execute(
        "INSERT INTO conversation_memories "
        "(id,conversation_id,index_id,predecessor_id,covered_through,input,"
        "input_sha256,source_tokens,policy,foreground) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        (
            uuid4(),
            conversation_id,
            index_id,
            predecessor,
            covered,
            Jsonb(source),
            hashlib.sha256(serialized.encode()).hexdigest(),
            count_tokens(serialized, policy["model_id"]),
            Jsonb(policy),
            foreground,
        ),
    )
    return conn.execute(
        "SELECT * FROM conversation_memories WHERE conversation_id=%s AND "
        "predecessor_id IS NOT DISTINCT FROM %s AND covered_through=%s",
        (conversation_id, predecessor, covered),
    ).fetchone()


def plan_background(database, limit=20):
    with database.transaction() as conn:
        identities = conn.execute(
            "SELECT DISTINCT t.conversation_id FROM conversation_turns t JOIN conversations c "
            "ON c.id=t.conversation_id "
            "WHERE t.memory_check_needed AND c.deleted_at IS NULL AND NOT EXISTS "
            "(SELECT 1 FROM conversation_memories m WHERE m.conversation_id=c.id AND m.state "
            "IN ('pending','running')) "
            "ORDER BY t.conversation_id LIMIT %s",
            (limit,),
        ).fetchall()
    for identity in identities:
        with database.transaction() as conn:
            chat = lock_conversation(conn, identity["conversation_id"])
            if not chat:
                continue
            if conn.execute(
                "SELECT 1 FROM conversation_memories WHERE conversation_id=%s AND state IN "
                "('pending','running')",
                (chat["id"],),
            ).fetchone():
                # Another planner may have started work after the initial unlocked scan.
                continue
            latest = conn.execute(
                "SELECT * FROM conversation_turns WHERE conversation_id=%s AND state NOT IN "
                "('pending','running') "
                "ORDER BY sequence DESC LIMIT 1",
                (chat["id"],),
            ).fetchone()
            if latest and "memory" in latest["policy"]:
                try:
                    plan(conn, chat["id"], chat["index_id"], latest["sequence"], latest["policy"])
                except (BudgetError, AdmissionError) as error:
                    log_event(
                        "chat_memory_planning_unavailable",
                        conversation_id=str(chat["id"]),
                        error_code=error.code,
                        error=error,
                    )
                conn.execute(
                    "UPDATE conversation_turns SET memory_check_needed=false WHERE "
                    "conversation_id=%s AND sequence<=%s",
                    (chat["id"], latest["sequence"]),
                )
