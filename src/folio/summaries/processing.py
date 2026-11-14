import logging

import psycopg

from folio.ai.openrouter import OpenRouter, ProviderError
from folio.ai.tokens import BudgetError, check_budget
from folio.config import Settings
from folio.database import Database
from folio.observability import configure_logging, log_event
from folio.summaries.config import SummaryCredentials
from folio.summaries.lifecycle import claim_run, finish, reserve_invocation
from folio.summaries.preparation import InvalidOutput, OutputLimit, prepare, validate_output


def process_summary(run_id, *, settings=None, client=None):
    configure_logging("summary_worker")
    settings = settings or Settings()
    database = Database(settings.database_url)
    database.open()
    try:
        claim = claim_run(database, run_id)
        if claim is None:
            return {"outcome": "ignored"}
        manifest, generation = None, None
        try:
            if (
                claim.policy["timeout_seconds"] + 30 >= claim.policy["job_timeout_seconds"]
                or claim.policy["lease_seconds"]
                <= claim.policy["job_timeout_seconds"] + 60 + settings.worker_monitor_seconds
            ):
                raise ProviderError("SUMMARY_EXECUTION_CONFIG_MISMATCH")
            if client is None:
                credential = SummaryCredentials().api_key.get_secret_value()
                if not credential:
                    raise ProviderError("SUMMARY_PROVIDER_NOT_CONFIGURED")
                client = OpenRouter(claim.policy, credential)
            messages, schema, manifest = prepare(database, claim.revision_id)
            profile = client.profile()
            manifest.update(check_budget(messages, schema, claim.policy, profile))
            manifest["profile"] = profile
            if claim.manifest is not None and manifest != claim.manifest:
                manifest = claim.manifest
                raise BudgetError("SUMMARY_SPECIFICATION_CHANGED")
            code = reserve_invocation(database, claim, manifest)
            if code == "SUPERSEDED":
                return {"outcome": "superseded"}
            if code:
                raise BudgetError(code)
            generation = client.generate(messages, schema)
            result = validate_output(generation, manifest["source_ids"])
        except BudgetError as error:
            finish(
                database,
                claim,
                manifest=manifest,
                code=error.code,
                state="unavailable",
                error=error,
            )
            return {"outcome": "unavailable", "code": error.code}
        except ProviderError as error:
            unavailable = error.code in {
                "SUMMARY_PROVIDER_NOT_CONFIGURED",
                "SUMMARY_MODEL_UNAVAILABLE",
                "SUMMARY_EXECUTION_CONFIG_MISMATCH",
            }
            state = "unavailable" if unavailable else "failed"
            finish(
                database,
                claim,
                manifest=manifest,
                code=error.code,
                state=state,
                retryable=error.retryable,
                generation=error.generation,
                error=error,
            )
            return {"outcome": state, "code": error.code}
        except OutputLimit as error:
            finish(
                database,
                claim,
                manifest=manifest,
                generation=generation,
                code="SUMMARY_OUTPUT_LIMIT",
                error=error,
            )
            return {"outcome": "failed", "code": "SUMMARY_OUTPUT_LIMIT"}
        except InvalidOutput as error:
            finish(
                database,
                claim,
                manifest=manifest,
                generation=generation,
                code="INVALID_OUTPUT",
                retryable=True,
                error=error,
            )
            return {"outcome": "failed", "code": "INVALID_OUTPUT"}
        except Exception as error:
            log_event(
                "summary_processing_error",
                attempt_id=claim.attempt_id,
                summary_run_id=str(claim.run_id),
                level=logging.ERROR,
                error=error,
                operation="summary_processing",
            )
            finish(
                database,
                claim,
                manifest=manifest,
                generation=generation,
                code="SUMMARY_PROCESSING_ERROR",
                retryable=isinstance(error, (OSError, psycopg.OperationalError)),
                error=error,
            )
            return {"outcome": "failed", "code": "SUMMARY_PROCESSING_ERROR"}
        published = finish(database, claim, result=result, manifest=manifest, generation=generation)
        log_event(
            "summary_finished",
            attempt_id=claim.attempt_id,
            summary_run_id=str(claim.run_id),
            outcome="ready" if published else "superseded",
        )
        return {"outcome": "ready" if published else "superseded"}
    finally:
        database.close()
