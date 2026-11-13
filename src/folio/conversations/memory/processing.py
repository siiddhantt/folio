from decimal import Decimal
from time import monotonic

import psycopg

from folio.ai import OpenRouter, check_budget
from folio.config import Settings
from folio.conversations.config import rewrite_policy
from folio.conversations.invocations import AdmissionError
from folio.database import Database
from folio.indexing.provider import OpenRouterEmbeddings
from folio.observability import configure_logging, log_event
from folio.summaries.config import SummaryCredentials

from .lifecycle import claim, fail_preflight, finish
from .preparation import prepare, validate


def process_memory(
    memory_id, *, settings=None, generator=None, answer_model=None, resolver=None, embedder=None
):
    settings = settings or Settings()
    configure_logging("memory_worker")
    database = Database(settings.database_url)
    database.open()
    claimed, generation, memory = None, None, None
    started = monotonic()
    try:
        with database.transaction() as conn:
            memory = conn.execute(
                "SELECT m.* FROM conversation_memories m JOIN conversations c ON "
                "c.id=m.conversation_id "
                "WHERE m.id=%s AND m.state='pending' AND m.available_at<=clock_timestamp() AND "
                "c.deleted_at IS NULL",
                (memory_id,),
            ).fetchone()
            if memory is None or (memory["deferred_reason"] and not memory["foreground"]):
                return {"outcome": "ignored"}
            index = conn.execute(
                "SELECT policy FROM document_indexes WHERE id=%s", (memory["index_id"],)
            ).fetchone()
        policy = memory["policy"]
        if (
            policy["timeout_seconds"] + 30 >= policy["job_timeout_seconds"]
            or policy["lease_seconds"]
            <= policy["job_timeout_seconds"] + 60 + settings.worker_monitor_seconds
        ):
            raise AdmissionError("MEMORY_EXECUTION_CONFIG_MISMATCH")
        key = SummaryCredentials().api_key.get_secret_value()
        if generator is None and not key:
            raise AdmissionError("MEMORY_PROVIDER_NOT_CONFIGURED")
        generator = generator or OpenRouter(policy, key)
        messages, schema = prepare(memory["input"], policy["notes_target_tokens"])
        profile = generator.profile()
        manifest = check_budget(messages, schema, policy, profile) | {
            "profile": profile,
            "input_sha256": memory["input_sha256"],
        }
        foreground = policy["foreground_policy"]
        resolving = rewrite_policy(foreground)
        amount = Decimal(0)
        for stage_policy, model in ((foreground, answer_model), (resolving, resolver)):
            same_route = all(
                stage_policy[k] == policy[k] for k in ("model_id", "provider", "reasoning_effort")
            )
            stage_profile = (
                model.profile()
                if model
                else profile
                if same_route
                else OpenRouter(stage_policy, key).profile()
            )
            reservation = check_budget(
                [{"role": "user", "content": "Question"}], {}, stage_policy, stage_profile
            )
            amount += Decimal(reservation["reservation_usd"])
        embedding_profile = (embedder or OpenRouterEmbeddings(index["policy"], key)).profile()
        amount += (
            Decimal(embedding_profile["max_input_tokens"])
            * Decimal(embedding_profile["input_price_per_million"])
            / 1_000_000
        )
        if monotonic() + policy["timeout_seconds"] >= started + policy["job_timeout_seconds"] - 30:
            raise AdmissionError("MEMORY_EXECUTION_TIME_LIMIT")
        claimed = claim(database, memory, manifest, amount)
        if claimed is None:
            return {"outcome": "deferred"}
        if isinstance(claimed, str):
            return {"outcome": "unavailable", "code": claimed}
        generation = generator.generate(messages, schema, schema_name="folio_memory")
        result, tokens = validate(
            generation,
            memory["input"],
            policy,
            memory["source_tokens"],
            memory_id=memory["id"],
            covered_through=memory["covered_through"],
        )
        state = finish(
            database, claimed, generation=generation, result=result, result_tokens=tokens
        )
        log_event("chat_memory_finished", memory_id=str(memory_id), outcome=state)
        return {"outcome": state}
    except Exception as error:
        if memory is None:
            raise
        code = getattr(
            error,
            "code",
            "MEMORY_OUTPUT_INVALID" if isinstance(error, ValueError) else "MEMORY_PROCESSING_ERROR",
        )
        if code.startswith("SUMMARY_"):
            code = "MEMORY_" + code.removeprefix("SUMMARY_")
        retryable = getattr(error, "retryable", False) or isinstance(
            error, (OSError, psycopg.OperationalError)
        )
        if claimed is None:
            state = fail_preflight(database, memory, code, error, retryable=retryable)
        else:
            state = finish(
                database,
                claimed,
                generation=getattr(error, "generation", None) or generation,
                code=code,
                error=error,
                retryable=retryable,
            )
        log_event("chat_memory_failed", memory_id=str(memory_id), error_code=code, outcome=state)
        return {"outcome": state, "code": code}
    finally:
        database.close()
