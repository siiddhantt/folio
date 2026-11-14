from dataclasses import dataclass
from decimal import Decimal

from psycopg.types.json import Jsonb

from folio.ai.budget import spending
from folio.indexing.config import capture_policy as capture_index_policy
from folio.storage import UploadError
from folio.summaries.config import SummarySettings, capture_policy

from .models import Controls, reasoning_options, summary_configuration_error


@dataclass(frozen=True)
class UploadConfiguration:
    max_upload_bytes: int
    processing: dict


def capture_upload(database, settings, idempotency_key):
    current = read_controls(database, settings)
    values = Controls.model_validate(current["values"])
    if values.parser_timeout_seconds >= settings.job_timeout_seconds:
        raise UploadError("Saved parser timeout exceeds the worker limit. Update settings.", 503)
    effective = settings.model_copy(
        update={
            "max_pages": values.max_pages,
            "parser_timeout_seconds": values.parser_timeout_seconds,
        }
    )
    policy = capture_policy(settings)
    if not policy.get("unavailable_code"):
        policy.update(
            {
                "enabled": values.summary_enabled,
                "input_limit_tokens": values.summary_input_limit_tokens,
                "max_output_tokens": values.summary_max_output_tokens,
                "reasoning_effort": values.summary_reasoning_effort,
            }
        )
    config = {
        **effective.processing_config(),
        "max_upload_bytes": values.max_upload_bytes,
        "settings_revision": current["revision"],
        "summary_policy": policy,
        "index_policy": capture_index_policy(settings),
    }
    limit = values.max_upload_bytes
    if idempotency_key and len(idempotency_key) <= 200:
        with database.transaction() as connection:
            previous = connection.execute(
                "SELECT f.byte_size FROM api_idempotency i "
                "JOIN ingestion_requests r ON r.id=i.request_id "
                "JOIN file_versions f ON f.id=r.file_version_id "
                "WHERE i.scope='local' AND i.operation='upload' AND i.key=%s",
                (idempotency_key,),
            ).fetchone()
        if previous:
            limit = max(limit, previous["byte_size"])
    return UploadConfiguration(limit, config)


def read_controls(database, settings):
    policy = capture_policy(settings)
    defaults = {
        "max_pages": settings.max_pages,
        "max_upload_bytes": settings.max_upload_bytes,
        "parser_timeout_seconds": settings.parser_timeout_seconds,
        **{
            f"summary_{key}": policy.get(key, SummarySettings.model_fields[key].default)
            for key in ("enabled", "input_limit_tokens", "max_output_tokens", "reasoning_effort")
        },
    }
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO runtime_configuration(id,values) VALUES (true,%s) ON CONFLICT DO NOTHING",
            (Jsonb(defaults),),
        )
        return connection.execute(
            "SELECT revision,values,updated_at FROM runtime_configuration WHERE id=true"
        ).fetchone()


def save_controls(database, settings, update):
    update.values.validate_runtime(settings, capture_policy(settings))
    with database.transaction() as connection:
        row = connection.execute(
            "UPDATE runtime_configuration SET values=%s,revision=revision+1,"
            "updated_at=clock_timestamp() WHERE id=true AND revision=%s "
            "RETURNING revision,values,updated_at",
            (Jsonb(update.values.model_dump()), update.revision),
        ).fetchone()
    return row


def describe(database, settings, current=None):
    if current is None:
        current = read_controls(database, settings)
    policy = capture_policy(settings)
    with database.transaction() as connection:
        account = connection.execute(
            "SELECT budget_usd,admission_error FROM summary_budget_account WHERE id=true"
        ).fetchone()
        used = spending(connection)
    allowance = Decimal(policy.get("budget_usd", "0"))
    if account:
        allowance = min(allowance, account["budget_usd"])
    return {
        **current,
        "runtime": {
            "model_id": policy.get("model_id"),
            "provider": policy.get("provider"),
            "token_margin": policy.get("token_margin"),
            "reasoning_options": reasoning_options(policy),
            "summary_configuration_error": summary_configuration_error(settings, policy),
            "job_timeout_seconds": settings.job_timeout_seconds,
            "lease_seconds": settings.lease_seconds,
            "summary_timeout_seconds": policy.get("timeout_seconds"),
            "document_budget_usd": policy.get("document_budget_usd"),
            "budget_usd": str(allowance),
            "admission_error": account["admission_error"] if account else None,
            "spent_usd": str(used["spent_usd"]),
            "held_usd": str(used["held_usd"]),
            "remaining_usd": str(max(Decimal(0), allowance - used["spent_usd"] - used["held_usd"])),
        },
    }
