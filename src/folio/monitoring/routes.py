from fastapi import APIRouter

from folio.database import Database
from folio.monitoring.models import DocumentStatistics, ProcessingMetrics
from folio.monitoring.queries import document_statistics, processing_metrics


def create_router(database: Database) -> APIRouter:
    router = APIRouter(tags=["Monitoring"])

    @router.get("/statistics/documents", response_model=DocumentStatistics)
    def statistics():
        """Count current documents and active extraction pages in one database snapshot.

        State maps omit zero-count states. No recovered content may mean a blank
        or unreadable page; recovered content does not prove complete extraction.
        """
        return document_statistics(database)

    @router.get("/metrics/processing", response_model=ProcessingMetrics)
    def metrics():
        """Aggregate all retained work, including work for removed conversations.

        Each stage counts durable jobs separately from execution attempts. Indexing
        attempts include successful batches, not just retries. Unfinished attempts
        include queued/interrupted work and do not measure active workers.
        Duration samples exclude missing or reversed timestamps, include failures,
        and exclude queue wait. Memory timing starts at invocation. A null mean/max
        means no samples. Terminal errors count failed/unavailable jobs only.
        """
        return processing_metrics(database)

    return router
