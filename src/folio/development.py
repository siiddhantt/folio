SAFE_CONFIGURATION = (
    "parser",
    "parser_version",
    "normalization_version",
    "max_pages",
    "timeout_seconds",
    "ocr_language",
    "lease_seconds",
    "job_timeout_seconds",
    "worker_monitor_seconds",
    "max_attempts",
    "retry_delays_seconds",
    "retry_jitter_seconds",
)


def inspect_request(database, request_id, after_id=0, limit=100):
    with database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        request = connection.execute(
            """SELECT id AS request_id,document_id,file_version_id,state,authorized_attempt_id,
            created_at,finished_at,requested_config FROM ingestion_requests WHERE id=%s""",
            (request_id,),
        ).fetchone()
        if request is None:
            return None
        config = request.pop("requested_config")
        request["configuration"] = {key: config[key] for key in SAFE_CONFIGURATION if key in config}
        request["source"] = connection.execute(
            "SELECT sha256,byte_size,media_type FROM file_versions WHERE id=%s",
            (request["file_version_id"],),
        ).fetchone()
        request["attempts"] = connection.execute(
            """SELECT id,attempt_no,state,available_at,started_at,finished_at,lease_expires_at,
            error_code,error_detail,parser_status,retryable,metrics,transport_job_id,
            last_dispatched_at,next_dispatch_at,dispatch_count,terminal_delivery_failures,
            dispatch_error FROM processing_attempts WHERE request_id=%s ORDER BY attempt_no""",
            (request_id,),
        ).fetchall()
        events = connection.execute(
            """SELECT id,attempt_id,name,occurred_at,details FROM processing_events
            WHERE request_id=%s AND id>%s ORDER BY id LIMIT %s""",
            (request_id, after_id, limit + 1),
        ).fetchall()
        request["events"] = events[:limit]
        request["next_after_id"] = events[limit - 1]["id"] if len(events) > limit else None
        return request
