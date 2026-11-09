import json
import logging

import psycopg
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)


def configure_logging():
    application = logging.getLogger("folio")
    application.setLevel(logging.INFO)
    application.propagate = False
    if not application.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        application.addHandler(handler)


def log_event(name, request_id, attempt_id=None, **details):
    logger.info(
        "%s",
        json.dumps(
            {
                "event": name,
                "request_id": str(request_id),
                "attempt_id": str(attempt_id) if attempt_id is not None else None,
                **details,
            }
        ),
    )


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
        logger.warning(
            "Event unavailable request_id=%s attempt_id=%s event=%s error=%s",
            request_id,
            attempt_id,
            name,
            type(error).__name__,
        )
        return False


def observe(database, claim, name, **details):
    from folio.ownership import locked_attempt, owns

    try:
        with locked_attempt(database, claim.request_id, claim.attempt_id) as (
            conn,
            request,
            attempt,
        ):
            if not owns(conn, request, attempt, claim.token):
                return False
            recorded = record_event(conn, claim.request_id, claim.attempt_id, name, **details)
        if recorded:
            log_event(name, claim.request_id, claim.attempt_id, **details)
        return recorded
    except psycopg.Error as error:
        logger.warning(
            "Observation unavailable request_id=%s attempt_id=%s event=%s error=%s",
            claim.request_id,
            claim.attempt_id,
            name,
            type(error).__name__,
        )
        return False
