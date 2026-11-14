from uuid import uuid4

from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer

from folio.config import Settings
from folio.database import Database

from .lifecycle import recover_expired
from .planning import plan_background


def queue_for(settings):
    return Queue(
        "memory",
        connection=Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1),
        serializer=JSONSerializer,
    )


def dispatch_once(settings=None):
    settings = settings or Settings()
    database, queue = Database(settings.database_url), queue_for(settings)
    database.open()
    delivered = []
    try:
        recover_expired(database, settings.batch_size)
        plan_background(database, settings.batch_size)
        with database.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM conversation_memories WHERE state='pending' AND deferred_reason "
                "IS NULL "
                "AND available_at<=clock_timestamp() AND next_dispatch_at<=clock_timestamp() "
                "ORDER BY next_dispatch_at,id LIMIT %s FOR UPDATE SKIP LOCKED",
                (settings.batch_size,),
            ).fetchall()
            for row in rows:
                conn.execute(
                    "UPDATE conversation_memories SET "
                    "next_dispatch_at=clock_timestamp()+%s*interval '1 second' WHERE id=%s",
                    (settings.dispatch_grace_seconds, row["id"]),
                )
        for row in rows:
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
                    terminal = failures >= settings.bootstrap_failure_limit
                    replacement = uuid4().hex
                    with database.transaction() as conn:
                        changed = conn.execute(
                            "UPDATE conversation_memories SET "
                            "transport_job_id=%s,delivery_failures=%s,state=%s,error_code=%s,"
                            "finished_at=CASE WHEN %s THEN clock_timestamp() END WHERE id=%s "
                            "AND state='pending' "
                            "AND deferred_reason IS NULL AND transport_job_id IS NOT DISTINCT "
                            "FROM %s",
                            (
                                replacement,
                                failures,
                                "failed" if terminal else "pending",
                                "MEMORY_DELIVERY_FAILED" if terminal else row["error_code"],
                                terminal,
                                row["id"],
                                job_id,
                            ),
                        ).rowcount
                    if not changed or terminal:
                        continue
                    job_id = replacement
                    queue.enqueue_call(
                        "folio.conversations.memory.processing.process_memory",
                        args=(str(row["id"]),),
                        job_id=job_id,
                        timeout=row["policy"]["job_timeout_seconds"],
                        result_ttl=86400,
                        failure_ttl=86400,
                    )
                    delivered.append({"memory_id": str(row["id"]), "job_id": job_id})
            except Exception as exc:
                error = type(exc).__name__
            with database.transaction() as conn:
                conn.execute(
                    "UPDATE conversation_memories SET dispatch_error=%s WHERE id=%s AND "
                    "state='pending' "
                    "AND transport_job_id IS NOT DISTINCT FROM %s",
                    (error, row["id"], job_id),
                )
        return delivered
    finally:
        database.close()
        queue.connection.close()
