import errno
import logging
from time import perf_counter

import psycopg

from folio.config import Settings
from folio.database import Database
from folio.observability import configure_logging, log_event, observe
from folio.ownership import claim_attempt
from folio.publication import publish
from folio.recovery import finish_failure
from folio.storage import Artifacts

logger = logging.getLogger(__name__)


def process_attempt(request_id, attempt_id, *, settings=None, parser=None):
    configure_logging()
    settings = settings or Settings()
    database = Database(settings.database_url)
    database.open()
    try:
        claim = claim_attempt(database, request_id, attempt_id)
        if claim is None:
            return {"outcome": "ignored"}
        log_event("processing_started", claim.request_id, claim.attempt_id)
        artifacts = Artifacts(settings.artifact_root)
        from folio.parsing.evidence import ExtractionError

        try:
            supervision_bound = (
                claim.config["job_timeout_seconds"] + 60 + settings.worker_monitor_seconds
            )
            if claim.config["lease_seconds"] <= supervision_bound:
                raise ExtractionError(
                    "EXECUTION_CONFIG_MISMATCH",
                    "Worker supervision exceeds this request's ownership budget",
                )
            if parser is None:
                from folio.parsing import parse_pdf

                parser = parse_pdf
            started = perf_counter()
            path = artifacts.verify(claim.file)
            observe(database, claim, "source_verified", duration_seconds=perf_counter() - started)
            observe(database, claim, "parse_started")
            started = perf_counter()
            extraction = parser(path, claim.config)
            observe(
                database,
                claim,
                "parse_completed",
                duration_seconds=perf_counter() - started,
                pages=len(extraction.pages),
                elements=len(extraction.elements),
                parser_status=extraction.parser_status,
            )
            started = perf_counter()
            raw = artifacts.save_result(extraction.raw)
            observe(database, claim, "raw_result_saved", duration_seconds=perf_counter() - started)
            revision_id = publish(database, claim, extraction, raw)
        except ExtractionError as exc:
            diagnostic = None
            try:
                diagnostic = artifacts.save_result(
                    {
                        "document": exc.raw,
                        "diagnostics": exc.diagnostics,
                        "parser_manifest": exc.parser_manifest,
                        "parser_status": exc.parser_status,
                        "error_code": exc.code,
                    }
                )
            except (OSError, ValueError, TypeError, MemoryError) as export_error:
                logger.warning(
                    "Diagnostic artifact unavailable request_id=%s attempt_id=%s error=%s",
                    claim.request_id,
                    claim.attempt_id,
                    type(export_error).__name__,
                )
            finish_failure(
                database, claim, exc.code, exc.message, exc.retryable, exc.parser_status, diagnostic
            )
            return {"outcome": "failed", "code": exc.code}
        except psycopg.OperationalError as exc:
            finish_failure(database, claim, "DATABASE_INTERRUPTED", type(exc).__name__, True)
            return {"outcome": "failed", "code": "DATABASE_INTERRUPTED"}
        except OSError as exc:
            resource_limit = exc.errno in (errno.ENOSPC, errno.ENOMEM, errno.EDQUOT)
            code = "RESOURCE_EXHAUSTED" if resource_limit else "IO_INTERRUPTED"
            finish_failure(database, claim, code, "Storage operation failed", not resource_limit)
            return {"outcome": "failed", "code": code}
        except Exception as exc:
            code = "RESOURCE_EXHAUSTED" if isinstance(exc, MemoryError) else "PROCESSING_ERROR"
            finish_failure(database, claim, code, type(exc).__name__, False)
            return {"outcome": "failed", "code": code}
        log_event(
            "processing_finished",
            claim.request_id,
            claim.attempt_id,
            outcome="published" if revision_id else "superseded",
        )
        return {
            "outcome": "published" if revision_id else "superseded",
            "revision_id": str(revision_id) if revision_id else None,
        }
    finally:
        database.close()
