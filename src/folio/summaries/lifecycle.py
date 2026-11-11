import random
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class Claim:
    run_id: object
    attempt_id: object
    token: object
    revision_id: object
    document_id: object
    policy: dict
    manifest: dict | None


def insert_intent(connection, revision_id, document_id, policy):
    """Called only inside the evidence-publication transaction."""
    enabled = policy["enabled"]
    connection.execute(
        """INSERT INTO summary_runs(id,revision_id,document_id,policy,state,error_code,finished_at)
        VALUES (%s,%s,%s,%s,%s,%s,CASE WHEN %s THEN NULL ELSE clock_timestamp() END)
        ON CONFLICT (revision_id) DO NOTHING""",
        (
            uuid4(),
            revision_id,
            document_id,
            Jsonb(policy),
            "pending" if enabled else "unavailable",
            None if enabled else policy.get("unavailable_code", "SUMMARY_DISABLED"),
            enabled,
        ),
    )


def claim_run(database, run_id):
    with database.transaction() as connection:
        run = connection.execute(
            "SELECT * FROM summary_runs WHERE id=%s AND state='pending' "
            "AND available_at<=clock_timestamp() FOR UPDATE",
            (run_id,),
        ).fetchone()
        if run is None:
            return None
        token, attempt_id = uuid4(), uuid4()
        connection.execute(
            """UPDATE summary_runs SET state='running',attempt_count=attempt_count+1,claim_token=%s,
            lease_expires_at=clock_timestamp()+%s*interval '1 second',
            started_at=COALESCE(started_at,clock_timestamp()),dispatch_error=NULL WHERE id=%s""",
            (token, run["policy"]["lease_seconds"], run_id),
        )
        connection.execute(
            "INSERT INTO summary_attempts(id,run_id,attempt_no,claim_token) VALUES (%s,%s,%s,%s)",
            (attempt_id, run_id, run["attempt_count"] + 1, token),
        )
        return Claim(
            run["id"],
            attempt_id,
            token,
            run["revision_id"],
            run["document_id"],
            run["policy"],
            run["input_manifest"],
        )


def owned(connection, claim):
    run = connection.execute(
        "SELECT * FROM summary_runs WHERE id=%s AND state='running' AND claim_token=%s FOR UPDATE",
        (claim.run_id, claim.token),
    ).fetchone()
    # The lock may have waited: check time after acquiring it, not in the initial predicate.
    if run is None:
        return None
    current = connection.execute("SELECT clock_timestamp() AS time").fetchone()["time"]
    return run if run["lease_expires_at"] > current else None


def reserve_invocation(database, claim, manifest):
    """Reserve and mark the possible external side effect before sending any bytes."""
    amount = Decimal(manifest["reservation_usd"])
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO summary_budget_account(id,budget_usd) VALUES (true,%s) "
            "ON CONFLICT DO NOTHING",
            (Decimal(claim.policy["budget_usd"]),),
        )
        account = connection.execute(
            "SELECT * FROM summary_budget_account WHERE id=true FOR UPDATE"
        ).fetchone()
        if owned(connection, claim) is None:
            return "SUPERSEDED"
        spent = connection.execute(
            """SELECT COALESCE(sum(COALESCE(a.cost_usd,a.reserved_usd)),0) AS total,
            COALESCE(sum(COALESCE(a.cost_usd,a.reserved_usd))
                FILTER (WHERE r.document_id=%s),0) AS document
            FROM summary_attempts a JOIN summary_runs r ON r.id=a.run_id""",
            (claim.document_id,),
        ).fetchone()
        if spent["document"] + amount > Decimal(claim.policy["document_budget_usd"]):
            return "SUMMARY_DOCUMENT_BUDGET"
        if spent["total"] + amount > min(
            account["budget_usd"], Decimal(claim.policy["budget_usd"])
        ):
            return "SUMMARY_GLOBAL_BUDGET"
        connection.execute(
            "UPDATE summary_attempts SET invoked_at=clock_timestamp(),reserved_usd=%s,"
            "billing_state='reserved' WHERE id=%s",
            (amount, claim.attempt_id),
        )
        connection.execute(
            "UPDATE summary_runs SET input_manifest=%s WHERE id=%s", (Jsonb(manifest), claim.run_id)
        )
    return None


def finish(
    database,
    claim,
    *,
    result=None,
    manifest=None,
    generation=None,
    code=None,
    state="failed",
    retryable=False,
):
    # A failed metadata request has not established a generation specification to freeze.
    if retryable and manifest is not None and "reservation_usd" not in manifest:
        manifest = None
    with database.transaction() as connection:
        # Admission and settlement serialize on the same row; no caller holds run then account.
        connection.execute(
            "SELECT id FROM summary_budget_account WHERE id=true FOR UPDATE"
        ).fetchone()
        run = owned(connection, claim)
        if run is None:
            return False
        usage = (
            {}
            if generation is None
            else {
                "prompt_tokens": generation.prompt_tokens,
                "completion_tokens": generation.completion_tokens,
                "model": generation.model,
                "provider": generation.provider,
            }
        )
        connection.execute(
            """UPDATE summary_attempts SET finished_at=clock_timestamp(),error_code=%s,
            usage=%s,response_id=%s,cost_usd=%s,
            billing_state=CASE WHEN %s::numeric IS NOT NULL THEN 'known'
                WHEN invoked_at IS NOT NULL THEN 'unknown' ELSE billing_state END WHERE id=%s""",
            (
                code,
                Jsonb(usage),
                generation.response_id if generation else None,
                generation.cost_usd if generation else None,
                generation.cost_usd if generation else None,
                claim.attempt_id,
            ),
        )
        _transition(
            connection,
            run,
            result=result,
            manifest=manifest,
            code=code,
            state=state,
            retryable=retryable,
        )
        return True


def _transition(
    connection, run, *, result=None, manifest=None, code=None, state="failed", retryable=False
):
    retry = retryable and run["attempt_count"] < run["policy"]["max_attempts"]
    delay = 0
    if retry:
        delays = run["policy"]["retry_delays_seconds"]
        delay = delays[min(run["attempt_count"] - 1, len(delays) - 1)]
        delay += random.uniform(0, run["policy"]["retry_jitter_seconds"])
    connection.execute(
        """UPDATE summary_runs SET state=%s,result=%s,input_manifest=COALESCE(%s,input_manifest),
        error_code=%s,finished_at=CASE WHEN %s THEN NULL ELSE clock_timestamp() END,
        available_at=clock_timestamp()+%s*interval '1 second',
        next_dispatch_at=clock_timestamp()+%s*interval '1 second',
        lease_expires_at=NULL,claim_token=NULL,transport_job_id=NULL,
        dispatch_token=NULL,dispatch_claim_until=NULL,delivery_failures=0 WHERE id=%s""",
        (
            "ready" if result else "pending" if retry else state,
            Jsonb(result) if result else None,
            Jsonb(manifest) if manifest else None,
            code,
            retry,
            delay,
            delay,
            run["id"],
        ),
    )


def recover_expired(database, limit=20):
    with database.transaction() as connection:
        runs = connection.execute(
            "SELECT * FROM summary_runs WHERE state='running' "
            "AND lease_expires_at<=clock_timestamp() "
            "ORDER BY lease_expires_at,id LIMIT %s FOR UPDATE SKIP LOCKED",
            (limit,),
        ).fetchall()
        for run in runs:
            connection.execute(
                """UPDATE summary_attempts SET finished_at=clock_timestamp(),
                error_code='SUMMARY_WORKER_LOST',
                billing_state=CASE WHEN invoked_at IS NOT NULL AND cost_usd IS NULL
                    THEN 'unknown' ELSE billing_state END
                WHERE run_id=%s AND claim_token=%s AND finished_at IS NULL""",
                (run["id"], run["claim_token"]),
            )
            _transition(connection, run, code="SUMMARY_WORKER_LOST", retryable=True)
    return len(runs)
