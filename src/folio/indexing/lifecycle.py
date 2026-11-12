"""Durable indexing claims, batch checkpoints and atomic publication."""

import hashlib
import json
from decimal import Decimal
from uuid import uuid4

from psycopg.types.json import Jsonb

from folio.ai.budget import admission_error, lock_account
from folio.observability import exception_details


def insert_intent(connection, revision_id, document_id, policy):
    enabled = policy.get("enabled", False)
    connection.execute(
        """INSERT INTO document_indexes(id,revision_id,document_id,policy,state,error_code)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (revision_id) DO NOTHING""",
        (
            uuid4(),
            revision_id,
            document_id,
            Jsonb(policy),
            "pending" if enabled else "unavailable",
            None if enabled else policy.get("unavailable_code", "INDEX_DISABLED"),
        ),
    )


def claim_index(database, index_id):
    with database.transaction() as conn:
        row = conn.execute(
            "SELECT * FROM document_indexes WHERE id=%s AND state='pending' "
            "AND available_at<=clock_timestamp() FOR UPDATE",
            (index_id,),
        ).fetchone()
        if row is None:
            return None
        row.update(token=uuid4(), attempt_id=uuid4())
        conn.execute(
            """UPDATE document_indexes SET state='running',claim_token=%s,
            attempt_count=attempt_count+1,started_at=COALESCE(started_at,clock_timestamp()),
            lease_expires_at=clock_timestamp()+%s*interval '1 second' WHERE id=%s""",
            (row["token"], row["policy"]["lease_seconds"], index_id),
        )
        conn.execute(
            "INSERT INTO indexing_attempts(id,index_id,attempt_no,token) VALUES (%s,%s,%s,%s)",
            (row["attempt_id"], index_id, row["attempt_count"] + 1, row["token"]),
        )
        return row


def owned(conn, claim):
    row = conn.execute(
        "SELECT * FROM document_indexes WHERE id=%s AND state='running' "
        "AND claim_token=%s FOR UPDATE",
        (claim["id"], claim["token"]),
    ).fetchone()
    if row is None:
        return None
    now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    return row if row["lease_expires_at"] > now else None


def save_plan(database, claim, plan):
    with database.transaction() as conn:
        if owned(conn, claim) is None:
            return False
        batch_size = claim["policy"]["batch_size"]
        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO index_chunks
                (index_id,revision_id,ordinal,batch_no,text,tokens,sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                [
                    (
                        claim["id"],
                        claim["revision_id"],
                        c["ordinal"],
                        (c["ordinal"] - 1) // batch_size + 1,
                        c["text"],
                        c["tokens"],
                        c["sha256"],
                    )
                    for c in plan["chunks"]
                ],
            )
            cursor.executemany(
                "INSERT INTO chunk_sources VALUES (%s,%s,%s,%s,%s,%s)",
                [
                    (
                        claim["id"],
                        claim["revision_id"],
                        c["ordinal"],
                        order,
                        s["element_id"],
                        s["role"],
                    )
                    for c in plan["chunks"]
                    for order, s in enumerate(c["sources"])
                ],
            )
        manifest = {key: value for key, value in plan.items() if key != "chunks"}
        conn.execute(
            "UPDATE document_indexes SET chunk_count=%s,manifest=%s WHERE id=%s",
            (len(plan["chunks"]), Jsonb(manifest), claim["id"]),
        )
    return True


def next_batch(database, claim):
    with database.transaction() as conn:
        return conn.execute(
            """SELECT ordinal,batch_no,text,tokens,sha256 FROM index_chunks WHERE index_id=%s
            AND batch_no=(SELECT min(batch_no) FROM index_chunks
                WHERE index_id=%s AND embedding IS NULL) ORDER BY ordinal""",
            (claim["id"], claim["id"]),
        ).fetchall()


def reserve_batch(database, claim, batch, profile):
    policy = claim["policy"]
    # The small margin covers counting discrepancies; actual reported cost replaces it.
    tokens = sum(c["tokens"] + 16 for c in batch)
    amount = Decimal(tokens) * Decimal(policy["input_price_per_million"]) / 1_000_000
    with database.transaction() as conn:
        limit = lock_account(conn, policy["budget_usd"])
        if owned(conn, claim) is None:
            return "SUPERSEDED"
        code = admission_error(
            conn, claim["document_id"], amount, limit, Decimal(policy["document_budget_usd"])
        )
        if code:
            return "INDEX_" + code
        metadata = {
            "profile": profile,
            "input_hash": hashlib.sha256(
                "\n".join(c["sha256"] for c in batch).encode()
            ).hexdigest(),
            "chunk_ordinals": [c["ordinal"] for c in batch],
            "input_tokens": tokens,
        }
        conn.execute(
            """INSERT INTO embedding_invocations(id,index_id,batch_no,attempt_id,reserved_usd,
            invoked_at,billing_state,metadata)
            VALUES (%s,%s,%s,%s,%s,clock_timestamp(),'reserved',%s)""",
            (
                uuid4(),
                claim["id"],
                batch[0]["batch_no"],
                claim["attempt_id"],
                amount,
                Jsonb(metadata),
            ),
        )
        conn.execute(
            "UPDATE indexing_attempts SET batch_no=%s WHERE id=%s",
            (batch[0]["batch_no"], claim["attempt_id"]),
        )
    return None


def _transition(conn, run, state, code=None, delay=0, failures=0):
    conn.execute(
        """UPDATE document_indexes SET state=%s,error_code=%s,failures=%s,
        finished_at=CASE WHEN %s IN ('ready','failed','unavailable') THEN clock_timestamp() END,
        available_at=clock_timestamp()+%s*interval '1 second',
        next_dispatch_at=clock_timestamp()+%s*interval '1 second',
        claim_token=NULL,lease_expires_at=NULL,transport_job_id=NULL,delivery_failures=0
        WHERE id=%s""",
        (state, code, failures, state, delay, delay, run["id"]),
    )


def finish(
    database,
    claim,
    *,
    batch=None,
    result=None,
    error=None,
    unavailable=False,
    diagnostic_error=None,
):
    with database.transaction() as conn:
        conn.execute("SELECT id FROM summary_budget_account WHERE id=true FOR UPDATE")
        cost = getattr(result or error, "cost_usd", None)
        metadata = getattr(result or error, "metadata", {})
        conn.execute(
            """UPDATE embedding_invocations
            SET cost_usd=COALESCE(cost_usd,%s),metadata=metadata || %s,
            finished_at=clock_timestamp(),billing_state=CASE WHEN COALESCE(cost_usd,%s) IS NULL
            THEN 'unknown' ELSE 'known' END WHERE attempt_id=%s AND index_id=%s""",
            (cost, Jsonb(metadata), cost, claim["attempt_id"], claim["id"]),
        )
        run = owned(conn, claim)
        if run is None:
            return "superseded"
        code = getattr(error, "code", None)
        if error is None:
            with conn.cursor() as cursor:
                cursor.executemany(
                    "UPDATE index_chunks SET embedding=%s::vector WHERE index_id=%s AND ordinal=%s",
                    [
                        (json.dumps(vector, allow_nan=False), claim["id"], chunk["ordinal"])
                        for chunk, vector in zip(batch, result.vectors, strict=True)
                    ],
                )
            counts = conn.execute(
                "SELECT count(*) AS total,count(*) FILTER (WHERE embedding IS NULL) AS remaining "
                "FROM index_chunks WHERE index_id=%s",
                (claim["id"],),
            ).fetchone()
            if counts["total"] != run["chunk_count"]:
                raise ValueError("Saved chunks differ from the immutable plan")
            state = "pending" if counts["remaining"] else "ready"
            _transition(conn, run, state)
        else:
            failures = run["failures"] + 1
            retry = getattr(error, "retryable", False) and failures < run["policy"]["max_attempts"]
            delays = run["policy"]["retry_delays_seconds"]
            delay = delays[min(failures - 1, len(delays) - 1)] if retry else 0
            state = "pending" if retry else "unavailable" if unavailable else "failed"
            _transition(conn, run, state, code, delay, failures)
        conn.execute(
            """UPDATE indexing_attempts SET state=%s,finished_at=clock_timestamp(),error_code=%s,
            failure_diagnostics=%s WHERE id=%s""",
            (
                "failed" if error else "succeeded",
                code,
                Jsonb(exception_details(diagnostic_error or error)) if error else None,
                claim["attempt_id"],
            ),
        )
        return state


def recover_expired(database, limit=20):
    with database.transaction() as conn:
        conn.execute("SELECT id FROM summary_budget_account WHERE id=true FOR UPDATE")
        rows = conn.execute(
            "SELECT * FROM document_indexes WHERE state='running' "
            "AND lease_expires_at<=clock_timestamp() "
            "ORDER BY lease_expires_at,id LIMIT %s FOR UPDATE SKIP LOCKED",
            (limit,),
        ).fetchall()
        for row in rows:
            conn.execute(
                """UPDATE embedding_invocations
                SET billing_state='unknown',finished_at=clock_timestamp()
                WHERE attempt_id IN
                    (SELECT id FROM indexing_attempts WHERE index_id=%s AND token=%s)
                AND cost_usd IS NULL""",
                (row["id"], row["claim_token"]),
            )
            conn.execute(
                "UPDATE indexing_attempts SET state='failed',finished_at=clock_timestamp(),"
                "error_code='INDEX_WORKER_LOST' WHERE index_id=%s AND token=%s",
                (row["id"], row["claim_token"]),
            )
            failures = row["failures"] + 1
            state = "pending" if failures < row["policy"]["max_attempts"] else "failed"
            _transition(conn, row, state, "INDEX_WORKER_LOST", failures=failures)
    return len(rows)
