from uuid import uuid4

from folio.config import Settings
from folio.database import Database
from folio.ingestion.dispatcher import queue_for

from .lifecycle import recover_expired


def dispatch_once(settings=None):
    settings = settings or Settings()
    database, queue = Database(settings.database_url), queue_for(settings)
    database.open()
    delivered = []
    try:
        recover_expired(database, settings.batch_size)
        with database.transaction() as conn:
            due = conn.execute(
                """SELECT * FROM document_indexes WHERE state='pending'
                AND available_at<=clock_timestamp() AND next_dispatch_at<=clock_timestamp()
                ORDER BY next_dispatch_at,id LIMIT %s FOR UPDATE SKIP LOCKED""",
                (settings.batch_size,),
            ).fetchall()
            for row in due:
                conn.execute(
                    "UPDATE document_indexes "
                    "SET next_dispatch_at=clock_timestamp()+%s*interval '1 second' "
                    "WHERE id=%s",
                    (settings.dispatch_grace_seconds, row["id"]),
                )
        for row in due:
            error, job_id = None, row["transport_job_id"]
            try:
                old = queue.fetch_job(job_id) if job_id else None
                status = old.get_status().value if old else None
                queued = status == "queued" and queue.get_job_position(old.id) is not None
                executing = status == "started" and bool(old.get_executions())
                if not (queued or executing):
                    failures = row["delivery_failures"] + int(
                        status in {"failed", "stopped", "canceled", "finished"}
                    )
                    replacement = uuid4().hex
                    terminal = failures >= settings.bootstrap_failure_limit
                    with database.transaction() as conn:
                        changed = conn.execute(
                            """UPDATE document_indexes SET transport_job_id=%s,delivery_failures=%s,
                            state=%s,error_code=%s,
                            finished_at=CASE WHEN %s THEN clock_timestamp() END
                            WHERE id=%s AND state='pending'
                            AND transport_job_id IS NOT DISTINCT FROM %s""",
                            (
                                replacement,
                                failures,
                                "failed" if terminal else "pending",
                                "INDEX_DELIVERY_FAILED" if terminal else row["error_code"],
                                terminal,
                                row["id"],
                                job_id,
                            ),
                        ).rowcount
                    if not changed or terminal:
                        continue
                    job_id = replacement
                    queue.enqueue_call(
                        "folio.indexing.processing.process_index",
                        args=(str(row["id"]),),
                        job_id=job_id,
                        timeout=row["policy"]["job_timeout_seconds"],
                        result_ttl=86400,
                        failure_ttl=86400,
                    )
                    delivered.append({"index_id": str(row["id"]), "job_id": job_id})
            except Exception as exc:
                error = type(exc).__name__
            with database.transaction() as conn:
                conn.execute(
                    "UPDATE document_indexes SET dispatch_error=%s WHERE id=%s AND state='pending' "
                    "AND transport_job_id IS NOT DISTINCT FROM %s",
                    (error, row["id"], job_id),
                )
        return delivered
    finally:
        database.close()
        queue.connection.close()
