from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID, uuid4

from folio.observability import record_event


@dataclass(frozen=True)
class Claim:
    request_id: UUID
    attempt_id: UUID
    token: UUID
    config: dict
    file: dict


@contextmanager
def locked_attempt(database, request_id, attempt_id):
    with database.transaction() as connection:
        identity = connection.execute(
            "SELECT document_id FROM ingestion_requests WHERE id=%s", (request_id,)
        ).fetchone()
        if identity is None:
            yield connection, None, None
            return
        connection.execute(
            "SELECT id FROM documents WHERE id=%s FOR UPDATE", (identity["document_id"],)
        ).fetchone()
        request = connection.execute(
            "SELECT * FROM ingestion_requests WHERE id=%s FOR UPDATE", (request_id,)
        ).fetchone()
        attempt = connection.execute(
            "SELECT * FROM processing_attempts WHERE id=%s AND request_id=%s FOR UPDATE",
            (attempt_id, request_id),
        ).fetchone()
        yield connection, request, attempt


def authorized(request, attempt):
    return (
        request is not None
        and attempt is not None
        and request["state"] == "open"
        and request["authorized_attempt_id"] == attempt["id"]
    )


def owns(connection, request, attempt, token):
    if not authorized(request, attempt) or attempt["state"] != "running":
        return False
    current = connection.execute("SELECT clock_timestamp() AS time").fetchone()["time"]
    return attempt["claim_token"] == token and attempt["lease_expires_at"] > current


def claim_attempt(database, request_id, attempt_id):
    with locked_attempt(database, request_id, attempt_id) as (connection, request, attempt):
        if not authorized(request, attempt) or attempt["state"] != "pending":
            return None
        token = uuid4()
        changed = connection.execute(
            """UPDATE processing_attempts SET state='running',claim_token=%s,
            started_at=clock_timestamp(),
            lease_expires_at=clock_timestamp() + %s * interval '1 second',
            dispatch_error=NULL WHERE id=%s AND available_at <= clock_timestamp() RETURNING id""",
            (token, request["requested_config"]["lease_seconds"], attempt_id),
        ).fetchone()
        if changed is None:
            return None
        file = connection.execute(
            "SELECT * FROM file_versions WHERE id=%s", (request["file_version_id"],)
        ).fetchone()
        record_event(connection, request["id"], attempt["id"], "worker_claimed")
        return Claim(request["id"], attempt["id"], token, request["requested_config"], file)
