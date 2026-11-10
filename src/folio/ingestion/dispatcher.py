import logging
import time
from uuid import uuid4

from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer

from folio.config import Settings
from folio.database import Database
from folio.ingestion.events import record_event
from folio.ingestion.ownership import authorized, locked_attempt
from folio.ingestion.recovery import recover_expired
from folio.observability import configure_logging, log_event


def queue_for(settings):
    return Queue(
        "ingestion",
        connection=Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=3,
            socket_timeout=5,
        ),
        serializer=JSONSerializer,
    )


def reserve_due(database, settings):
    with database.transaction() as conn:
        candidates = conn.execute(
            """SELECT r.id AS request_id,a.id AS attempt_id
            FROM documents d JOIN ingestion_requests r ON r.document_id=d.id
            JOIN processing_attempts a ON a.id=r.authorized_attempt_id
            WHERE r.state='open' AND a.state='pending' AND a.available_at<=clock_timestamp()
            AND a.next_dispatch_at<=clock_timestamp()
            AND (a.dispatch_claim_until IS NULL OR a.dispatch_claim_until<=clock_timestamp())
            ORDER BY a.next_dispatch_at,a.id LIMIT %s FOR UPDATE OF d SKIP LOCKED""",
            (settings.batch_size,),
        ).fetchall()
        reserved = []
        for candidate in candidates:
            request = conn.execute(
                "SELECT * FROM ingestion_requests WHERE id=%s FOR UPDATE",
                (candidate["request_id"],),
            ).fetchone()
            attempt = conn.execute(
                "SELECT * FROM processing_attempts WHERE id=%s FOR UPDATE",
                (candidate["attempt_id"],),
            ).fetchone()
            if not authorized(request, attempt) or attempt["state"] != "pending":
                continue
            token = uuid4()
            row = conn.execute(
                """UPDATE processing_attempts SET dispatch_token=%s,
                dispatch_claim_until=clock_timestamp()+%s*interval '1 second'
                WHERE id=%s AND next_dispatch_at<=clock_timestamp()
                AND available_at<=clock_timestamp()
                AND (dispatch_claim_until IS NULL OR dispatch_claim_until<=clock_timestamp())
                RETURNING *""",
                (token, settings.dispatch_grace_seconds, attempt["id"]),
            ).fetchone()
            if row:
                row["requested_config"] = request["requested_config"]
                reserved.append(row)
        return reserved


def prepare_delivery(database, row, settings, terminal_failure):
    with locked_attempt(database, row["request_id"], row["id"]) as (conn, request, attempt):
        if (
            not authorized(request, attempt)
            or attempt["state"] != "pending"
            or attempt["dispatch_token"] != row["dispatch_token"]
        ):
            return None
        failures = attempt["terminal_delivery_failures"] + int(terminal_failure)
        if failures >= settings.bootstrap_failure_limit:
            conn.execute(
                """UPDATE processing_attempts SET state='failed',error_code='DELIVERY_FAILED',
                error_detail='Repeated queue execution failures before processing could start',
                retryable=false,finished_at=clock_timestamp(),terminal_delivery_failures=%s,
                dispatch_claim_until=NULL WHERE id=%s""",
                (failures, attempt["id"]),
            )
            conn.execute(
                "UPDATE ingestion_requests SET state='failed',finished_at=clock_timestamp() "
                "WHERE id=%s",
                (request["id"],),
            )
            record_event(
                conn,
                request["id"],
                attempt["id"],
                "attempt_failed",
                error_code="DELIVERY_FAILED",
                retryable=False,
            )
            return None
        job_id = uuid4().hex
        # Consuming the previous terminal delivery and reserving its replacement are atomic.
        conn.execute(
            """UPDATE processing_attempts SET transport_job_id=%s,terminal_delivery_failures=%s,
            dispatch_count=dispatch_count+1 WHERE id=%s""",
            (job_id, failures, attempt["id"]),
        )
        record_event(
            conn, request["id"], attempt["id"], "delivery_requested", transport_job_id=job_id
        )
        return job_id


def acknowledge(database, row, settings, job_id, error, enqueued):
    with locked_attempt(database, row["request_id"], row["id"]) as (conn, request, attempt):
        if (
            not authorized(request, attempt)
            or attempt["state"] != "pending"
            or attempt["dispatch_token"] != row["dispatch_token"]
            or attempt["transport_job_id"] != job_id
        ):
            return
        conn.execute(
            """UPDATE processing_attempts SET dispatch_error=%s,
            last_dispatched_at=CASE WHEN %s
                THEN clock_timestamp() ELSE last_dispatched_at END,
            next_dispatch_at=clock_timestamp()+%s*interval '1 second',dispatch_claim_until=NULL
            WHERE id=%s AND state='pending' AND dispatch_token=%s
            AND transport_job_id IS NOT DISTINCT FROM %s""",
            (
                error,
                enqueued,
                settings.dispatch_grace_seconds,
                row["id"],
                row["dispatch_token"],
                job_id,
            ),
        )
        if error != attempt["dispatch_error"]:
            record_event(
                conn,
                request["id"],
                attempt["id"],
                "delivery_deferred" if error else "delivery_resumed",
                error_code=error,
            )


def dispatch_once(settings=None):
    configure_logging("dispatcher")
    settings = settings or Settings()
    database = Database(settings.database_url)
    database.open()
    queue = queue_for(settings)
    deliveries = []
    try:
        recover_expired(database, settings.batch_size)
        for row in reserve_due(database, settings):
            error, job_id = None, row["transport_job_id"]
            enqueued = False
            try:
                old = queue.fetch_job(job_id) if job_id else None
                status = old.get_status().value if old else None
                queued = status == "queued" and queue.get_job_position(old.id) is not None
                executing = status == "started" and bool(old.get_executions())
                if not (queued or executing):
                    terminal = status in ("failed", "stopped", "canceled", "finished")
                    job_id = prepare_delivery(database, row, settings, terminal)
                    if job_id is None:
                        continue
                    queue.enqueue_call(
                        "folio.processing.process_attempt",
                        args=(str(row["request_id"]), str(row["id"])),
                        job_id=job_id,
                        timeout=row["requested_config"]["job_timeout_seconds"],
                        result_ttl=86400,
                        failure_ttl=86400,
                    )
                    enqueued = True
                    deliveries.append({"request_id": str(row["request_id"]), "job_id": job_id})
            except Exception as exc:
                error = type(exc).__name__
                log_event(
                    "delivery_deferred",
                    row["request_id"],
                    row["id"],
                    level=logging.WARNING,
                    error=exc,
                    operation="queue_delivery",
                    transport_job_id=job_id,
                )
            acknowledge(database, row, settings, job_id, error, enqueued)
        return deliveries
    finally:
        database.close()
        queue.connection.close()


def run():
    settings = Settings()
    while True:
        try:
            dispatch_once(settings)
        except Exception as exc:
            log_event(
                "recovery_cycle_unavailable",
                level=logging.ERROR,
                error=exc,
                operation="dispatch",
            )
        time.sleep(settings.recovery_interval_seconds)
