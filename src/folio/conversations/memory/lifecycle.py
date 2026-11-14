"""Memory ownership and paid-call settlement share the conversation/account gates."""

from decimal import Decimal
from uuid import uuid4

from psycopg.types.json import Jsonb

from folio.ai.budget import admission_error, check_settlement, lock_account
from folio.ai.generation import generation_usage
from folio.conversations.context import latest_memory
from folio.conversations.lifecycle import lock_conversation
from folio.observability import exception_details


def claim(database, memory, manifest, foreground_allowance):
    with database.transaction() as conn:
        allowance = lock_account(conn, memory["policy"]["budget_usd"])
        if lock_conversation(conn, memory["conversation_id"]) is None:
            return None
        row = conn.execute(
            "SELECT * FROM conversation_memories WHERE id=%s AND state='pending' "
            "AND available_at<=clock_timestamp() FOR UPDATE",
            (memory["id"],),
        ).fetchone()
        if row is None or (row["deferred_reason"] and not row["foreground"]):
            return None
        if row["input_manifest"] is not None and row["input_manifest"] != manifest:
            conn.execute(
                "UPDATE conversation_memories SET "
                "state='unavailable',error_code='MEMORY_SPECIFICATION_CHANGED',"
                "finished_at=clock_timestamp(),transport_job_id=NULL WHERE id=%s",
                (row["id"],),
            )
            return "MEMORY_SPECIFICATION_CHANGED"
        document = conn.execute(
            "SELECT document_id FROM document_indexes WHERE id=%s", (row["index_id"],)
        ).fetchone()
        amount = Decimal(manifest["reservation_usd"])
        code = admission_error(
            conn,
            document["document_id"],
            amount + (Decimal(0) if row["foreground"] else foreground_allowance),
            allowance,
            row["policy"]["document_budget_usd"],
        )
        if code:
            if row["foreground"]:
                conn.execute(
                    "UPDATE conversation_memories SET state='unavailable',error_code=%s,"
                    "finished_at=clock_timestamp(),transport_job_id=NULL,deferred_reason=NULL "
                    "WHERE id=%s",
                    ("MEMORY_" + code, row["id"]),
                )
                return "MEMORY_" + code
            conn.execute(
                "UPDATE conversation_memories SET deferred_reason=%s,transport_job_id=NULL "
                "WHERE id=%s",
                (code, row["id"]),
            )
            return None
        row.update(token=uuid4(), attempt_id=uuid4())
        conn.execute(
            "UPDATE conversation_memories SET "
            "state='running',claim_token=%s,attempt_count=attempt_count+1,"
            "started_at=COALESCE(started_at,clock_timestamp()),"
            "lease_expires_at=clock_timestamp()+%s*interval '1 second',"
            "input_manifest=%s,deferred_reason=NULL WHERE id=%s",
            (row["token"], row["policy"]["lease_seconds"], Jsonb(manifest), row["id"]),
        )
        conn.execute(
            "INSERT INTO "
            "memory_attempts(id,memory_id,attempt_no,token,reserved_usd,reserved_input,metadata) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                row["attempt_id"],
                row["id"],
                row["attempt_count"] + 1,
                row["token"],
                amount,
                manifest["input_tokens_reserved"],
                Jsonb(manifest),
            ),
        )
        row["attempt_count"] += 1
        return row


def owned(conn, claim):
    if lock_conversation(conn, claim["conversation_id"]) is None:
        return None
    row = conn.execute(
        "SELECT * FROM conversation_memories WHERE id=%s AND state='running' AND "
        "claim_token=%s FOR UPDATE",
        (claim["id"], claim["token"]),
    ).fetchone()
    return (
        row
        if row
        and row["lease_expires_at"]
        > conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        else None
    )


def transition(conn, row, *, result=None, result_tokens=None, code=None, retryable=False):
    retry = retryable and row["attempt_count"] < row["policy"]["max_attempts"]
    delay = row["policy"]["retry_delays_seconds"][0] if retry else 0
    state = "ready" if result else "pending" if retry else "failed"
    conn.execute(
        "UPDATE conversation_memories SET state=%s,result=%s,result_tokens=%s,error_code=%s,"
        "claim_token=NULL,lease_expires_at=NULL,finished_at=CASE WHEN %s THEN NULL ELSE "
        "clock_timestamp() END,"
        "available_at=clock_timestamp()+%s*interval '1 "
        "second',next_dispatch_at=clock_timestamp()+%s*interval '1 second',"
        "transport_job_id=NULL,delivery_failures=0 WHERE id=%s",
        (
            state,
            Jsonb(result) if result else None,
            result_tokens,
            code,
            retry,
            delay,
            delay,
            row["id"],
        ),
    )
    return state


def finish(
    database,
    claim,
    *,
    generation=None,
    result=None,
    result_tokens=None,
    code=None,
    error=None,
    retryable=False,
):
    with database.transaction() as conn:
        conn.execute("SELECT id FROM summary_budget_account WHERE id=true FOR UPDATE")
        row = owned(conn, claim)
        metadata = (
            getattr(error, "metadata", {}) if generation is None else generation_usage(generation)
        )
        cost = generation.cost_usd if generation else getattr(error, "cost_usd", None)
        charge = conn.execute(
            "UPDATE memory_attempts SET cost_usd=COALESCE(cost_usd,%s),"
            "metadata=CASE WHEN cost_usd IS NULL THEN metadata || jsonb_strip_nulls(%s) ELSE "
            "metadata END,"
            "billing_state=CASE WHEN cost_usd IS NOT NULL THEN billing_state "
            "WHEN COALESCE(cost_usd,%s) IS NULL THEN 'unknown' "
            "WHEN %s='token_estimate' THEN 'estimated' ELSE 'known' END,"
            "finished_at=clock_timestamp(),error_code=COALESCE(error_code,%s),"
            "failure_diagnostics=COALESCE(failure_diagnostics,%s) "
            "WHERE id=%s AND memory_id=%s AND token=%s RETURNING *",
            (
                cost,
                Jsonb(metadata),
                cost,
                metadata.get("cost_basis", "provider_reported"),
                code,
                Jsonb(exception_details(error)) if error else None,
                claim["attempt_id"],
                claim["id"],
                claim["token"],
            ),
        ).fetchone()
        if charge:
            check_settlement(
                conn,
                reserved_usd=charge["reserved_usd"],
                cost_usd=charge["cost_usd"],
                reserved_input=charge["reserved_input"],
                reported_input=charge["metadata"].get("prompt_tokens"),
            )
        if row is None:
            return "superseded"
        active = latest_memory(conn, row["conversation_id"], 2147483647)
        if result and (active["id"] if active else None) != (
            str(row["predecessor_id"]) if row["predecessor_id"] else None
        ):
            result, result_tokens, code, retryable = None, None, "MEMORY_PREDECESSOR_CHANGED", False
        return transition(
            conn, row, result=result, result_tokens=result_tokens, code=code, retryable=retryable
        )


def recover_expired(database, limit=20):
    with database.transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM conversation_memories WHERE state='running' AND "
            "lease_expires_at<=clock_timestamp() "
            "ORDER BY lease_expires_at,id LIMIT %s FOR UPDATE SKIP LOCKED",
            (limit,),
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE memory_attempts SET "
                "finished_at=clock_timestamp(),error_code='MEMORY_WORKER_LOST',"
                "billing_state=CASE WHEN cost_usd IS NULL THEN 'unknown' ELSE billing_state END "
                "WHERE memory_id=%s AND token=%s",
                (row["id"], row["claim_token"]),
            )
            transition(conn, row, code="MEMORY_WORKER_LOST", retryable=True)
    return len(rows)


def fail_preflight(database, memory, code, error, *, retryable=False):
    with database.transaction() as conn:
        if lock_conversation(conn, memory["conversation_id"]) is None:
            return "superseded"
        row = conn.execute(
            "SELECT * FROM conversation_memories WHERE id=%s AND state='pending' FOR UPDATE",
            (memory["id"],),
        ).fetchone()
        if row is None:
            return "superseded"
        failures = row["preflight_failures"] + 1
        retry = retryable and failures < row["policy"]["max_attempts"]
        delay = row["policy"]["retry_delays_seconds"][0] if retry else 0
        state = "pending" if retry else "unavailable"
        conn.execute(
            "UPDATE conversation_memories SET "
            "state=%s,preflight_failures=%s,error_code=%s,dispatch_error=%s,"
            "available_at=clock_timestamp()+%s*interval '1 "
            "second',next_dispatch_at=clock_timestamp()+%s*interval '1 second',"
            "transport_job_id=NULL,finished_at=CASE WHEN %s THEN NULL ELSE clock_timestamp() "
            "END WHERE id=%s",
            (state, failures, code, type(error).__name__, delay, delay, retry, row["id"]),
        )
        return state


def cancel(conn, conversation_id):
    """The caller holds the conversation gate; already admitted calls can still settle."""
    rows = conn.execute(
        "UPDATE conversation_memories SET state='unavailable',error_code='MEMORY_CHAT_DELETED',"
        "claim_token=NULL,lease_expires_at=NULL,transport_job_id=NULL,"
        "finished_at=clock_timestamp() "
        "WHERE conversation_id=%s AND state IN ('pending','running') RETURNING id",
        (conversation_id,),
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE memory_attempts SET "
            "finished_at=clock_timestamp(),error_code='MEMORY_CHAT_DELETED',"
            "billing_state=CASE WHEN cost_usd IS NULL THEN 'unknown' ELSE billing_state END "
            "WHERE memory_id=%s AND finished_at IS NULL",
            (row["id"],),
        )
