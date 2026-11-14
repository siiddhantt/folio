import logging

import psycopg

from folio.config import Settings
from folio.database import Database
from folio.observability import configure_logging, log_event
from folio.summaries.config import SummaryCredentials

from .chunking import ChunkingError
from .lifecycle import claim_index, finish, next_batch, reserve_batch, save_plan
from .preparation import prepare
from .provider import EmbeddingError, OpenRouterEmbeddings


def process_index(index_id, *, settings=None, client=None):
    """Prepare once, then checkpoint one bounded embedding batch per delivery."""
    configure_logging("index_worker")
    settings = settings or Settings()
    database = Database(settings.database_url)
    database.open()
    claim, result = None, None
    try:
        claim = claim_index(database, index_id)
        if claim is None:
            return {"outcome": "ignored"}
        policy = claim["policy"]
        try:
            if (
                policy["timeout_seconds"] + 30 >= policy["job_timeout_seconds"]
                or policy["lease_seconds"]
                <= policy["job_timeout_seconds"] + 60 + settings.worker_monitor_seconds
            ):
                raise EmbeddingError("INDEX_EXECUTION_CONFIG_MISMATCH")
            if claim["chunk_count"] is None:
                plan = prepare(database, claim, settings.artifact_root)
                if not save_plan(database, claim, plan):
                    return {"outcome": "superseded"}
            batch = next_batch(database, claim)
            if not batch:
                raise EmbeddingError("INDEX_PLAN_INVALID")
            if client is None:
                key = SummaryCredentials().api_key.get_secret_value()
                if not key:
                    raise EmbeddingError("EMBEDDING_PROVIDER_NOT_CONFIGURED")
                client = OpenRouterEmbeddings(policy, key)
            profile = client.profile()
            if (
                profile["model_id"] != policy["model_id"]
                or profile["dimensions"] != policy["dimensions"]
                or profile["provider"] != policy["provider"]
            ):
                raise EmbeddingError("EMBEDDING_MODEL_UNAVAILABLE")
            code = reserve_batch(database, claim, batch, profile)
            if code == "SUPERSEDED":
                return {"outcome": "superseded"}
            if code:
                raise EmbeddingError(code)
            result = client.embed([chunk["text"] for chunk in batch])
            state = finish(database, claim, batch=batch, result=result)
        except (ChunkingError, EmbeddingError) as error:
            unavailable = error.code in {
                "INDEX_DOCUMENT_BUDGET",
                "INDEX_GLOBAL_BUDGET",
                "INDEX_RESERVATION_EXCEEDED",
                "INDEX_CHUNK_LIMIT",
                "EMBEDDING_PROVIDER_NOT_CONFIGURED",
                "EMBEDDING_MODEL_UNAVAILABLE",
                "INDEX_EXECUTION_CONFIG_MISMATCH",
            }
            state = finish(database, claim, error=error, unavailable=unavailable)
        except Exception as error:
            failure = EmbeddingError(
                "INDEX_PROCESSING_ERROR",
                retryable=isinstance(error, (OSError, psycopg.OperationalError)),
                metadata=getattr(result, "metadata", {}),
                cost_usd=getattr(result, "cost_usd", None),
            )
            state = finish(database, claim, error=failure, diagnostic_error=error)
            log_event(
                "index_processing_error",
                level=logging.ERROR,
                error=error,
                index_id=str(index_id),
                attempt_id=claim["attempt_id"],
            )
        log_event(
            "index_batch_finished",
            index_id=str(index_id),
            attempt_id=claim["attempt_id"],
            outcome=state,
        )
        return {"outcome": state}
    finally:
        database.close()
