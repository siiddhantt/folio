"""Bounded accepted-upload history; execution details remain in request inspection."""

import base64
import json
from datetime import datetime
from uuid import UUID


def list_requests(database, limit=25, before=None):
    position = _decode_cursor(before) if before is not None else None
    predicate = "WHERE (created_at,id)<(%s,%s)" if position else ""
    parameters = (*position, limit + 1) if position else (limit + 1,)
    with database.transaction() as connection:
        rows = connection.execute(
            f"""WITH page AS (
                SELECT * FROM ingestion_requests {predicate}
                ORDER BY created_at DESC,id DESC LIMIT %s
            )
            SELECT r.id AS request_id,r.document_id,x.id AS revision_id,
                f.original_filename AS filename,r.created_at AS accepted_at,
                r.state AS extraction_state,a.state AS current_attempt_state,
                a.error_code AS extraction_error_code,
                COALESCE(s.state,'not_scheduled') AS summary_state,
                s.error_code AS summary_error_code
            FROM page r
            JOIN file_versions f ON f.id=r.file_version_id
            JOIN processing_attempts a ON a.id=r.authorized_attempt_id
            LEFT JOIN extraction_revisions x ON x.request_id=r.id
            LEFT JOIN summary_runs s ON s.revision_id=x.id
            ORDER BY r.created_at DESC,r.id DESC""",
            parameters,
        ).fetchall()
    items = rows[:limit]
    return {
        "items": items,
        "next_cursor": _encode_cursor(items[-1]) if len(rows) > limit else None,
    }


def _encode_cursor(item):
    value = [item["accepted_at"].isoformat(), str(item["request_id"])]
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()


def _decode_cursor(cursor):
    try:
        value = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(isinstance(part, str) for part in value)
        ):
            raise ValueError
        timestamp, request_id = datetime.fromisoformat(value[0]), UUID(value[1])
        if timestamp.tzinfo is None:
            raise ValueError
        return timestamp, request_id
    except (ValueError, TypeError) as error:
        raise ValueError("Invalid history cursor") from error
