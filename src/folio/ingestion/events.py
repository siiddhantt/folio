"""Best-effort ingestion events recorded beside authoritative state changes."""

import logging

import psycopg
from psycopg.types.json import Jsonb

from folio.observability import log_event


def record_event(connection, request_id, attempt_id, name, **details):
    """Hold the request lock; a savepoint isolates recoverable event-insert SQL errors."""
    try:
        with connection.transaction():
            connection.execute(
                """INSERT INTO processing_events(request_id,attempt_id,name,details)
                VALUES (%s,%s,%s,%s)""",
                (request_id, attempt_id, name, Jsonb(details)),
            )
        return True
    except psycopg.Error as error:
        log_event(
            "event_unavailable",
            request_id,
            attempt_id,
            level=logging.WARNING,
            observed_event=name,
            error=error,
            operation="record_event",
        )
        return False
