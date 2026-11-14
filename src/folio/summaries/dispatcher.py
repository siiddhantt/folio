import logging
import time
from uuid import uuid4

from folio.config import Settings
from folio.database import Database
from folio.ingestion.dispatcher import dispatch_once as dispatch_ingestion
from folio.ingestion.dispatcher import queue_for
from folio.observability import configure_logging, log_event
from folio.summaries.lifecycle import recover_expired


def _reserve(database, settings):
    with database.transaction() as connection:
        runs = connection.execute(
            """SELECT * FROM summary_runs WHERE state='pending' AND available_at<=clock_timestamp()
            AND next_dispatch_at<=clock_timestamp()
            AND (dispatch_claim_until IS NULL OR dispatch_claim_until<=clock_timestamp())
            ORDER BY next_dispatch_at,id LIMIT %s FOR UPDATE SKIP LOCKED""",
            (settings.batch_size,),
        ).fetchall()
        for run in runs:
            run["dispatch_token"] = uuid4()
            connection.execute(
                "UPDATE summary_runs SET dispatch_token=%s,"
                "dispatch_claim_until=clock_timestamp()+%s*interval '1 second' WHERE id=%s",
                (run["dispatch_token"], settings.dispatch_grace_seconds, run["id"]),
            )
    return runs


def _new_delivery(database, reserved, terminal, settings):
    with database.transaction() as connection:
        run = connection.execute(
            "SELECT * FROM summary_runs WHERE id=%s AND state='pending' "
            "AND dispatch_token=%s FOR UPDATE",
            (reserved["id"], reserved["dispatch_token"]),
        ).fetchone()
        if run is None:
            return None
        failures = run["delivery_failures"] + int(terminal)
        if failures >= settings.bootstrap_failure_limit:
            connection.execute(
                "UPDATE summary_runs SET state='failed',error_code='SUMMARY_DELIVERY_FAILED',"
                "finished_at=clock_timestamp(),delivery_failures=%s,"
                "dispatch_claim_until=NULL WHERE id=%s",
                (failures, run["id"]),
            )
            return None
        job_id = uuid4().hex
        connection.execute(
            "UPDATE summary_runs SET transport_job_id=%s,delivery_failures=%s WHERE id=%s",
            (job_id, failures, run["id"]),
        )
        return job_id


def dispatch_once(settings=None):
    configure_logging("dispatcher")
    settings = settings or Settings()
    database = Database(settings.database_url)
    database.open()
    queue = queue_for(settings)
    delivered = []
    try:
        recover_expired(database, settings.batch_size)
        for run in _reserve(database, settings):
            error, job_id = None, run["transport_job_id"]
            try:
                old = queue.fetch_job(job_id) if job_id else None
                status = old.get_status().value if old else None
                queued = status == "queued" and queue.get_job_position(old.id) is not None
                executing = status == "started" and bool(old.get_executions())
                if not (queued or executing):
                    job_id = _new_delivery(
                        database,
                        run,
                        status in ("failed", "stopped", "canceled", "finished"),
                        settings,
                    )
                    if job_id is None:
                        continue
                    queue.enqueue_call(
                        "folio.summaries.processing.process_summary",
                        args=(str(run["id"]),),
                        job_id=job_id,
                        timeout=run["policy"]["job_timeout_seconds"],
                        result_ttl=86400,
                        failure_ttl=86400,
                    )
                    delivered.append({"run_id": str(run["id"]), "job_id": job_id})
            except Exception as exc:
                error = type(exc).__name__
                log_event(
                    "summary_delivery_deferred",
                    level=logging.WARNING,
                    error=exc,
                    summary_run_id=str(run["id"]),
                    operation="summary_queue_delivery",
                )
            with database.transaction() as connection:
                connection.execute(
                    """UPDATE summary_runs SET dispatch_error=%s,
                    next_dispatch_at=clock_timestamp()+%s*interval '1 second',
                    dispatch_claim_until=NULL WHERE id=%s AND state='pending' AND dispatch_token=%s
                    AND transport_job_id IS NOT DISTINCT FROM %s""",
                    (
                        error,
                        settings.dispatch_grace_seconds,
                        run["id"],
                        run["dispatch_token"],
                        job_id,
                    ),
                )
        return delivered
    finally:
        database.close()
        queue.connection.close()


def run():
    from folio.conversations.dispatcher import dispatch_once as dispatch_chats
    from folio.conversations.memory.dispatcher import dispatch_once as dispatch_memories
    from folio.indexing.dispatcher import dispatch_once as dispatch_indexes

    settings = Settings()
    while True:
        for operation in (
            dispatch_ingestion,
            dispatch_once,
            dispatch_indexes,
            dispatch_chats,
            dispatch_memories,
        ):
            try:
                operation(settings)
            except Exception as error:
                log_event(
                    "recovery_cycle_unavailable",
                    level=logging.ERROR,
                    error=error,
                    operation=operation.__module__,
                )
        time.sleep(settings.recovery_interval_seconds)
