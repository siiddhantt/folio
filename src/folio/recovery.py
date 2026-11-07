import random
from uuid import uuid4

from folio.ownership import authorized, locked_attempt, owns


def finish_failure(database, claim, code, message, retryable, parser_status=None, diagnostic=None):
    with locked_attempt(database, claim.request_id, claim.attempt_id) as (conn, request, attempt):
        if not owns(conn, request, attempt, claim.token):
            return False
        _record_failure(conn, request, attempt, code, message, retryable, parser_status, diagnostic)
        return True


def _record_failure(
    conn, request, attempt, code, message, retryable, parser_status=None, diagnostic=None
):
    conn.execute(
        """UPDATE processing_attempts SET state='failed',finished_at=clock_timestamp(),
        error_code=%s,error_detail=%s,retryable=%s,parser_status=%s,
        diagnostic_storage_key=%s,diagnostic_sha256=%s WHERE id=%s""",
        (
            code,
            message[:500],
            retryable,
            parser_status,
            diagnostic.key if diagnostic else None,
            diagnostic.sha256 if diagnostic else None,
            attempt["id"],
        ),
    )
    config = request["requested_config"]
    if retryable and attempt["attempt_no"] < config["max_attempts"]:
        delays = config["retry_delays_seconds"]
        delay = delays[min(attempt["attempt_no"] - 1, len(delays) - 1)]
        delay += random.uniform(0, config["retry_jitter_seconds"])
        next_id = uuid4()
        conn.execute(
            """INSERT INTO processing_attempts
            (id,request_id,attempt_no,available_at,next_dispatch_at)
            VALUES (%s,%s,%s,clock_timestamp()+%s*interval '1 second',
            clock_timestamp()+%s*interval '1 second')""",
            (next_id, request["id"], attempt["attempt_no"] + 1, delay, delay),
        )
        conn.execute(
            "UPDATE ingestion_requests SET authorized_attempt_id=%s WHERE id=%s",
            (next_id, request["id"]),
        )
    else:
        conn.execute(
            "UPDATE ingestion_requests SET state='failed',finished_at=clock_timestamp() "
            "WHERE id=%s",
            (request["id"],),
        )


def recover_expired(database, limit=20):
    with database.transaction() as conn:
        candidates = conn.execute(
            """SELECT id,request_id FROM processing_attempts WHERE state='running'
            AND lease_expires_at<=clock_timestamp() ORDER BY lease_expires_at,id LIMIT %s""",
            (limit,),
        ).fetchall()
    recovered = 0
    for candidate in candidates:
        with locked_attempt(database, candidate["request_id"], candidate["id"]) as (
            conn,
            request,
            attempt,
        ):
            if not authorized(request, attempt) or attempt["state"] != "running":
                continue
            now = conn.execute("SELECT clock_timestamp() AS time").fetchone()["time"]
            if attempt["lease_expires_at"] > now:
                continue
            _record_failure(
                conn,
                request,
                attempt,
                "WORKER_LOST",
                "Worker ownership expired before a result was published",
                True,
            )
            recovered += 1
    return recovered
