from uuid import uuid4

from psycopg.types.json import Jsonb

from folio.observability import exception_details


def lock_conversation(conn, conversation_id):
    """Account, when needed, precedes this gate; turn locks always follow it."""
    row = conn.execute(
        "SELECT * FROM conversations WHERE id=%s FOR UPDATE", (conversation_id,)
    ).fetchone()
    return row if row and row["deleted_at"] is None else None


def claim_turn(database, turn_id):
    with database.transaction() as conn:
        identity = conn.execute(
            "SELECT conversation_id FROM conversation_turns WHERE id=%s", (turn_id,)
        ).fetchone()
        if not identity or lock_conversation(conn, identity["conversation_id"]) is None:
            return None
        row = conn.execute(
            "SELECT * FROM conversation_turns WHERE id=%s AND state='pending' "
            "AND available_at<=clock_timestamp() "
            "AND (NOT policy ? 'memory' OR context_snapshot IS NOT NULL) FOR UPDATE",
            (turn_id,),
        ).fetchone()
        if row is None:
            return None
        row.update(token=uuid4(), attempt_id=uuid4())
        conn.execute(
            "UPDATE conversation_turns SET "
            "state='running',claim_token=%s,attempt_count=attempt_count+1,"
            "started_at=COALESCE(started_at,clock_timestamp()),lease_expires_at=clock_timestamp()+%s*interval"
            " '1 second' WHERE id=%s",
            (row["token"], row["policy"]["lease_seconds"], turn_id),
        )
        conn.execute(
            "INSERT INTO turn_attempts(id,turn_id,token,attempt_no) VALUES (%s,%s,%s,%s)",
            (row["attempt_id"], turn_id, row["token"], row["attempt_count"] + 1),
        )
        return row


def owned(conn, claim):
    if lock_conversation(conn, claim["conversation_id"]) is None:
        return None
    row = conn.execute(
        "SELECT * FROM conversation_turns WHERE id=%s AND state='running' AND "
        "claim_token=%s FOR UPDATE",
        (claim["id"], claim["token"]),
    ).fetchone()
    if (
        row
        and row["lease_expires_at"]
        > conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    ):
        return row
    return None


def transition(conn, row, *, result=None, code=None, retryable=False, unavailable=False):
    retry = retryable and row["attempt_count"] < row["policy"]["max_attempts"]
    delay = row["policy"]["retry_delays_seconds"][0] if retry else 0
    state = (
        "ready" if result else "pending" if retry else "unavailable" if unavailable else "failed"
    )
    conn.execute(
        "UPDATE conversation_turns SET "
        "state=%s,result=%s,error_code=%s,claim_token=NULL,lease_expires_at=NULL,"
        "finished_at=CASE WHEN %s THEN NULL ELSE clock_timestamp() END,"
        "available_at=clock_timestamp()+%s*interval '1 "
        "second',next_dispatch_at=clock_timestamp()+%s*interval '1 second',"
        "transport_job_id=NULL,delivery_failures=0,memory_check_needed=%s WHERE id=%s",
        (
            state,
            Jsonb(result) if result else None,
            code,
            retry,
            delay,
            delay,
            not retry and "memory" in row["policy"],
            row["id"],
        ),
    )
    return state


def fail(database, claim, code, *, error=None, retryable=False, unavailable=False):
    with database.transaction() as conn:
        row = owned(conn, claim)
        if row is None:
            return "superseded"
        conn.execute(
            "UPDATE turn_attempts SET "
            "finished_at=clock_timestamp(),error_code=%s,failure_diagnostics=%s WHERE "
            "id=%s",
            (code, Jsonb(exception_details(error)) if error else None, claim["attempt_id"]),
        )
        return transition(conn, row, code=code, retryable=retryable, unavailable=unavailable)


def recover_expired(database, limit=20):
    with database.transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM conversation_turns WHERE state='running' AND "
            "lease_expires_at<=clock_timestamp() "
            "ORDER BY lease_expires_at,id LIMIT %s FOR UPDATE SKIP LOCKED",
            (limit,),
        ).fetchall()
        for row in rows:
            attempt = conn.execute(
                "UPDATE turn_attempts SET "
                "finished_at=clock_timestamp(),error_code='CHAT_WORKER_LOST' "
                "WHERE turn_id=%s AND token=%s RETURNING id",
                (row["id"], row["claim_token"]),
            ).fetchone()
            conn.execute(
                "UPDATE turn_invocations SET billing_state='unknown',finished_at=clock_timestamp() "
                "WHERE attempt_id=%s AND cost_usd IS NULL",
                (attempt["id"],),
            )
            transition(conn, row, code="CHAT_WORKER_LOST", retryable=True)
    return len(rows)
