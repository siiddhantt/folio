import hashlib
import json
from decimal import Decimal
from time import monotonic

import psycopg
import tiktoken
from psycopg.types.json import Jsonb

from folio.ai import BudgetError, OpenRouter, check_budget
from folio.config import Settings
from folio.database import Database
from folio.indexing.provider import OpenRouterEmbeddings
from folio.observability import configure_logging, log_event
from folio.summaries.config import SummaryCredentials
from folio.summaries.preparation import coverage

from .invocations import AdmissionError, reserve, settle
from .lifecycle import claim_turn, fail, owned
from .preparation import prepare, validate
from .retrieval import retrieve


def generation_usage(result):
    return {
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "reasoning_tokens": getattr(result, "reasoning_tokens", None),
        "finish_reason": result.finish_reason,
        "model": result.model,
        "provider": result.provider,
        "response_id": result.response_id,
    }


def process_turn(turn_id, *, settings=None, embedder=None, generator=None):
    started = monotonic()
    settings = settings or Settings()
    configure_logging("chat_worker")
    database = Database(settings.database_url)
    database.open()
    claim, stage, result = None, None, None
    try:
        claim = claim_turn(database, turn_id)
        if claim is None:
            return {"outcome": "ignored"}
        policy = claim["policy"]
        deadline = started + policy["job_timeout_seconds"] - 30
        with database.transaction() as conn:
            index = conn.execute(
                "SELECT * FROM document_indexes WHERE id=%s", (claim["index_id"],)
            ).fetchone()
            revision = conn.execute(
                "SELECT id,diagnostics FROM extraction_revisions WHERE id=%s",
                (index["revision_id"],),
            ).fetchone()
            gaps = coverage(conn, revision)
        if (
            policy["timeout_seconds"] + index["policy"]["timeout_seconds"] + 30
            >= policy["job_timeout_seconds"]
            or policy["lease_seconds"]
            <= policy["job_timeout_seconds"] + 60 + settings.worker_monitor_seconds
        ):
            raise AdmissionError("CHAT_EXECUTION_CONFIG_MISMATCH")
        key = SummaryCredentials().api_key.get_secret_value()
        if claim["query_vector"] is None:
            if embedder is None:
                if not key:
                    raise AdmissionError("CHAT_PROVIDER_NOT_CONFIGURED")
                embedder = OpenRouterEmbeddings(index["policy"], key)
            profile = embedder.profile()
            if any(
                profile[k] != index["policy"][k] for k in ("model_id", "provider", "dimensions")
            ):
                raise AdmissionError("CHAT_EMBEDDING_SPACE_CHANGED")
            tokens = (
                len(tiktoken.get_encoding("cl100k_base").encode_ordinary(claim["question"])) + 16
            )
            if tokens > profile["max_input_tokens"]:
                raise AdmissionError("CHAT_INPUT_LIMIT")
            amount = Decimal(tokens) * Decimal(profile["input_price_per_million"]) / 1_000_000
            ensure_time(deadline, index["policy"]["timeout_seconds"])
            reserve(database, claim, "embedding", amount, tokens, {"profile": profile})
            stage = "embedding"
            result = embedder.embed([claim["question"]])
            if not settle(
                database,
                claim,
                stage,
                cost=result.cost_usd,
                metadata=result.metadata,
                vector=result.vectors[0],
            ):
                return {"outcome": "superseded"}
            stage, result = None, None
        passages = retrieve(database, claim)
        if passages is None:
            return {"outcome": "superseded"}
        if not passages:
            raise AdmissionError("CHAT_EVIDENCE_UNAVAILABLE")
        messages, schema = prepare(claim["question"], passages, gaps)
        if generator is None:
            if not key:
                raise AdmissionError("CHAT_PROVIDER_NOT_CONFIGURED")
            generator = OpenRouter(policy, key)
        profile = generator.profile()
        manifest = check_budget(messages, schema, policy, profile) | {
            "profile": profile,
            "input_sha256": hashlib.sha256(
                json.dumps([messages, schema], sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
        }
        with database.transaction() as conn:
            row = owned(conn, claim)
            if row is None:
                return {"outcome": "superseded"}
            if row["input_manifest"] is not None and row["input_manifest"] != manifest:
                raise AdmissionError("CHAT_SPECIFICATION_CHANGED")
            conn.execute(
                "UPDATE conversation_turns SET input_manifest=%s WHERE id=%s",
                (Jsonb(manifest), claim["id"]),
            )
        ensure_time(deadline, policy["timeout_seconds"])
        reserve(
            database,
            claim,
            "answer",
            manifest["reservation_usd"],
            manifest["input_tokens_reserved"],
            manifest,
        )
        stage = "answer"
        result = generator.generate(messages, schema, schema_name="folio_answer")
        answer = validate(result, passages)
        published = settle(
            database,
            claim,
            stage,
            cost=result.cost_usd,
            metadata=generation_usage(result),
            answer=answer,
        )
        log_event(
            "chat_turn_finished",
            turn_id=str(turn_id),
            outcome="ready" if published else "superseded",
        )
        return {"outcome": "ready" if published else "superseded"}
    except Exception as error:
        if claim is None:
            raise
        if stage:
            billed = getattr(error, "generation", None) or result
            cost = getattr(billed or error, "cost_usd", None)
            metadata = (
                generation_usage(billed)
                if stage == "answer" and billed
                else getattr(billed or error, "metadata", {})
            )
            settle(database, claim, stage, cost=cost, metadata=metadata)
        code = getattr(error, "code", None)
        if code and code.startswith("SUMMARY_"):
            code = "CHAT_" + code.removeprefix("SUMMARY_")
        elif code and code.startswith("EMBEDDING_"):
            code = "CHAT_" + code
        elif not code:
            code = (
                "CHAT_OUTPUT_INVALID" if isinstance(error, ValueError) else "CHAT_PROCESSING_ERROR"
            )
        state = fail(
            database,
            claim,
            code,
            error=error,
            retryable=getattr(error, "retryable", False)
            or isinstance(error, (OSError, psycopg.OperationalError)),
            unavailable=isinstance(error, (AdmissionError, BudgetError)),
        )
        log_event("chat_turn_failed", turn_id=str(turn_id), error_code=code, outcome=state)
        return {"outcome": state, "code": code}
    finally:
        database.close()


def ensure_time(deadline, timeout):
    if monotonic() + timeout >= deadline:
        raise AdmissionError("CHAT_EXECUTION_TIME_LIMIT")
