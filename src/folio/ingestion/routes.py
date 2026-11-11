"""HTTP interface for PDF upload, processing state, and source evidence."""

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers, UploadFile
from starlette.formparsers import MultiPartException

from folio.configuration.store import capture_upload
from folio.ingestion.acceptance import accept_pdf
from folio.ingestion.development import inspect_request
from folio.ingestion.queries import (
    document_metadata,
    original_file,
    request_status,
    revision_evidence,
)
from folio.storage import UploadError


class UploadLimit:
    def __init__(self, app, database, settings):
        self.app, self.database, self.settings = app, database, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/documents" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        try:
            configuration = await run_in_threadpool(
                capture_upload,
                self.database,
                self.settings,
                Headers(scope=scope).get("idempotency-key"),
            )
        except UploadError as error:
            return await JSONResponse({"detail": str(error)}, status_code=error.status_code)(
                scope, receive, send
            )
        scope["folio_configuration"] = configuration
        limit = configuration.max_upload_bytes + 65536
        total, exceeded = 0, False

        async def bounded_receive():
            nonlocal total, exceeded
            message = await receive()
            total += len(message.get("body", b""))
            if total > limit:
                exceeded = True
                # Starlette closes already-spooled files when multipart parsing raises this.
                raise MultiPartException("Request body exceeds the upload limit")
            return message

        async def bounded_send(message):
            if exceeded and message["type"] == "http.response.start":
                message["status"] = 413
            await send(message)

        await self.app(scope, bounded_receive, bounded_send)


def create_router(database, artifacts, settings):
    router = APIRouter()

    if settings.development_mode:

        @router.get("/development/ingestion-requests/{request_id}")
        def development(
            request_id: UUID, after_id: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)
        ):
            return required(inspect_request(database, request_id, after_id, limit))

    @router.post(
        "/documents",
        status_code=202,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {"file": {"type": "string", "format": "binary"}},
                        }
                    }
                },
            }
        },
    )
    async def upload(request: Request, idempotency_key: str = Header(min_length=1, max_length=200)):
        async with request.form(max_files=1, max_fields=0) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile) or not file.filename:
                raise HTTPException(422, "Provide one PDF in the file field")
            if len(file.filename) > 255:
                raise HTTPException(422, "Filename must be at most 255 characters")
            return await run_in_threadpool(
                accept_pdf,
                database,
                artifacts,
                file.file,
                file.filename,
                idempotency_key,
                request.scope["folio_configuration"],
            )

    @router.get("/ingestion-requests/{request_id}")
    def status(request_id: UUID):
        return required(request_status(database, request_id))

    @router.get("/documents/{document_id}")
    def document(document_id: UUID):
        return required(document_metadata(database, document_id))

    @router.get("/documents/{document_id}/original")
    def original(document_id: UUID, inline: bool = False):
        stored = required(original_file(database, document_id))
        return FileResponse(
            artifacts.path(stored["storage_key"]),
            media_type="application/pdf",
            filename=stored["original_filename"],
            content_disposition_type="inline" if inline else "attachment",
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @router.get("/revisions/{revision_id}/evidence")
    def evidence(
        revision_id: UUID, after_order: int = Query(-1, ge=-1), limit: int = Query(50, ge=1, le=100)
    ):
        return required(revision_evidence(database, revision_id, after_order, limit))

    return router


def required(value):
    if value is None:
        raise HTTPException(404, "Not found")
    return value
