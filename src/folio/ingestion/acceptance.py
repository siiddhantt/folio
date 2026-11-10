import hashlib
import json
from uuid import uuid4

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from folio.ingestion.events import record_event
from folio.observability import log_event
from folio.storage import UploadError


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def accept_pdf(database, artifacts, stream, filename, key, settings) -> dict:
    artifact = artifacts.save_pdf(stream, settings.max_upload_bytes)
    identity = fingerprint([artifact.sha256, artifact.byte_size, filename, {}])
    document_id, file_id, request_id, attempt_id = (uuid4() for _ in range(4))
    config = settings.processing_config()
    try:
        with database.transaction() as connection:
            connection.execute(
                "INSERT INTO documents(id, display_name) VALUES (%s, %s)", (document_id, filename)
            )
            connection.execute(
                """INSERT INTO file_versions
                (id, document_id, original_filename, media_type, byte_size, sha256, storage_key)
                VALUES (%s,%s,%s,'application/pdf',%s,%s,%s)""",
                (file_id, document_id, filename, artifact.byte_size, artifact.sha256, artifact.key),
            )
            connection.execute(
                """INSERT INTO ingestion_requests
                (id, document_id, file_version_id, requested_config, config_hash)
                VALUES (%s,%s,%s,%s,%s)""",
                (request_id, document_id, file_id, Jsonb(config), fingerprint(config)),
            )
            connection.execute(
                "INSERT INTO processing_attempts(id,request_id,attempt_no) VALUES (%s,%s,1)",
                (attempt_id, request_id),
            )
            connection.execute(
                "UPDATE ingestion_requests SET authorized_attempt_id=%s WHERE id=%s",
                (attempt_id, request_id),
            )
            connection.execute(
                "UPDATE documents SET current_request_id=%s WHERE id=%s", (request_id, document_id)
            )
            connection.execute(
                """INSERT INTO api_idempotency(scope,operation,key,request_fingerprint,request_id)
                VALUES ('local','upload',%s,%s,%s)""",
                (key, identity, request_id),
            )
            record_event(connection, request_id, attempt_id, "accepted")
    except UniqueViolation as error:
        if error.diag.constraint_name != "api_idempotency_pkey":
            raise
        # The losing transaction has rolled back in full; only its own file is removable.
        artifacts.discard(artifact.key)
        with database.transaction() as connection:
            previous = connection.execute(
                """SELECT i.request_fingerprint,r.document_id,r.file_version_id,r.id AS request_id
                FROM api_idempotency i JOIN ingestion_requests r ON r.id=i.request_id
                WHERE i.scope='local' AND i.operation='upload' AND i.key=%s""",
                (key,),
            ).fetchone()
        if previous["request_fingerprint"] != identity:
            raise UploadError("Idempotency key was already used for different input", 409) from None
        document_id, file_id, request_id = (
            previous["document_id"],
            previous["file_version_id"],
            previous["request_id"],
        )
    # Other database errors can include an uncertain COMMIT. Preserve the file for recovery.
    log_event("upload_receipt", request_id, document_id=str(document_id))
    return {
        "document_id": document_id,
        "file_version_id": file_id,
        "request_id": request_id,
        "status_url": f"/ingestion-requests/{request_id}",
    }
