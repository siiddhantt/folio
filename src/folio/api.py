from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from folio.acceptance import accept_pdf
from folio.config import Settings
from folio.database import Database
from folio.queries import document_metadata, original_file, request_status, revision_evidence
from folio.storage import Artifacts, UploadError


class UploadLimit:
    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        total, exceeded = 0, False

        async def bounded_receive():
            nonlocal total, exceeded
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.limit:
                exceeded = True
                # Starlette closes already-spooled files when multipart parsing raises this.
                raise MultiPartException("Request body exceeds the upload limit")
            return message

        async def bounded_send(message):
            if exceeded and message["type"] == "http.response.start":
                message["status"] = 413
            await send(message)

        await self.app(scope, bounded_receive, bounded_send)


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    database, artifacts = Database(settings.database_url), Artifacts(settings.artifact_root)

    @asynccontextmanager
    async def lifespan(app):
        database.open()
        yield
        database.close()

    app = FastAPI(title="Folio", version="0.1.0", lifespan=lifespan)
    app.add_middleware(UploadLimit, limit=settings.max_upload_bytes + 65536)

    @app.exception_handler(UploadError)
    async def upload_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=error.status_code)

    @app.get("/health")
    def health():
        with database.transaction() as connection:
            connection.execute("SELECT 1")
        return {"status": "ok"}

    @app.post(
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
                accept_pdf, database, artifacts, file.file, file.filename, idempotency_key, settings
            )

    @app.get("/ingestion-requests/{request_id}")
    def status(request_id: UUID):
        return required(request_status(database, request_id))

    @app.get("/documents/{document_id}")
    def document(document_id: UUID):
        return required(document_metadata(database, document_id))

    @app.get("/documents/{document_id}/original")
    def original(document_id: UUID):
        stored = required(original_file(database, document_id))
        return FileResponse(
            artifacts.path(stored["storage_key"]),
            media_type="application/pdf",
            filename=stored["original_filename"],
        )

    @app.get("/revisions/{revision_id}/evidence")
    def evidence(
        revision_id: UUID, after_order: int = Query(-1, ge=-1), limit: int = Query(50, ge=1, le=100)
    ):
        return required(revision_evidence(database, revision_id, after_order, limit))

    return app


def required(value):
    if value is None:
        raise HTTPException(404, "Not found")
    return value
