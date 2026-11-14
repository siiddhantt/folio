from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from folio.config import Settings
from folio.configuration.routes import create_router as create_configuration_router
from folio.configuration.store import read_controls
from folio.conversations.routes import create_router as create_conversation_router
from folio.database import Database
from folio.indexing.routes import create_router as create_index_router
from folio.ingestion.routes import UploadLimit, create_router
from folio.monitoring.routes import create_router as create_monitoring_router
from folio.observability import configure_logging
from folio.storage import Artifacts, UploadError
from folio.summaries.routes import create_router as create_summary_router


class Health(BaseModel):
    status: Literal["ok"]


class Capabilities(BaseModel):
    max_upload_bytes: int = Field(examples=[26214400])
    max_pages: int = Field(examples=[100])
    development_mode: bool


def create_app(settings: Settings | None = None):
    configure_logging("api")
    settings = settings or Settings()
    database, artifacts = Database(settings.database_url), Artifacts(settings.artifact_root)

    @asynccontextmanager
    async def lifespan(app):
        database.open()
        yield
        database.close()

    app = FastAPI(title="Folio", version="0.1.0", lifespan=lifespan)
    app.add_middleware(UploadLimit, database=database, settings=settings)

    @app.exception_handler(UploadError)
    async def upload_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=error.status_code)

    @app.get("/health", responses={200: {"model": Health}})
    def health():
        """Check API/database connectivity, not worker or model health."""
        with database.transaction() as connection:
            connection.execute("SELECT 1")
        return {"status": "ok"}

    @app.get("/capabilities", responses={200: {"model": Capabilities}})
    def capabilities():
        """Read effective upload limits; acceptance still requires worker validation."""
        controls = read_controls(database, settings)["values"]
        return {
            "max_upload_bytes": controls["max_upload_bytes"],
            "max_pages": controls["max_pages"],
            "development_mode": settings.development_mode,
        }

    app.include_router(create_router(database, artifacts, settings))
    app.include_router(create_summary_router(database))
    app.include_router(create_index_router(database, settings))
    app.include_router(create_conversation_router(database, settings))
    app.include_router(create_monitoring_router(database))
    if settings.development_mode:
        app.include_router(create_configuration_router(database, settings))
    return app
