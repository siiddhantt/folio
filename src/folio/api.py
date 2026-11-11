from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from folio.config import Settings
from folio.configuration.routes import create_router as create_configuration_router
from folio.configuration.store import read_controls
from folio.database import Database
from folio.ingestion.routes import UploadLimit, create_router
from folio.observability import configure_logging
from folio.storage import Artifacts, UploadError
from folio.summaries.routes import create_router as create_summary_router


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

    @app.get("/health")
    def health():
        with database.transaction() as connection:
            connection.execute("SELECT 1")
        return {"status": "ok"}

    @app.get("/capabilities")
    def capabilities():
        controls = read_controls(database, settings)["values"]
        return {
            "max_upload_bytes": controls["max_upload_bytes"],
            "max_pages": controls["max_pages"],
            "development_mode": settings.development_mode,
        }

    app.include_router(create_router(database, artifacts, settings))
    app.include_router(create_summary_router(database))
    if settings.development_mode:
        app.include_router(create_configuration_router(database, settings))
    return app
