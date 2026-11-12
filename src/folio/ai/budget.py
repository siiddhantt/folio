"""Shared paid-call bookkeeping and deployment admission, independent of prompts."""

from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BudgetSettings(BaseSettings):
    # Preserve existing environment names and the account's previously spent allowance.
    model_config = SettingsConfigDict(env_prefix="FOLIO_SUMMARY_", env_file=".env", extra="ignore")
    budget_usd: Decimal = Field(default=Decimal("1"), gt=0)
    document_budget_usd: Decimal = Field(default=Decimal("0.40"), gt=0)


def lock_account(connection, configured_limit):
    """Hold before a run/index lock; reserve or settle within this transaction."""
    configured_limit = Decimal(configured_limit)
    if not configured_limit.is_finite() or configured_limit <= 0:
        raise ValueError("The spending allowance must be finite and positive")
    # Retain the original account row so adding embeddings cannot reset its allowance.
    connection.execute(
        "INSERT INTO summary_budget_account(id,budget_usd) VALUES (true,%s) ON CONFLICT DO NOTHING",
        (configured_limit,),
    )
    account = connection.execute(
        "SELECT budget_usd FROM summary_budget_account WHERE id=true FOR UPDATE"
    ).fetchone()
    return min(configured_limit, account["budget_usd"])


def spending(connection, document_id=None):
    """Unknown charges retain the full reservation until a known cost replaces it."""
    return connection.execute(
        """WITH charges AS (
            SELECT r.document_id,a.cost_usd,a.reserved_usd
            FROM summary_attempts a JOIN summary_runs r ON r.id=a.run_id
            UNION ALL
            SELECT i.document_id,a.cost_usd,a.reserved_usd
            FROM embedding_invocations a JOIN document_indexes i ON i.id=a.index_id
            UNION ALL
            SELECT i.document_id,a.cost_usd,a.reserved_usd
            FROM turn_invocations a JOIN conversation_turns t ON t.id=a.turn_id
            JOIN document_indexes i ON i.id=t.index_id
        )
        SELECT COALESCE(sum(cost_usd),0) AS spent_usd,
            COALESCE(sum(reserved_usd) FILTER (WHERE cost_usd IS NULL),0) AS held_usd,
            COALESCE(sum(COALESCE(cost_usd,reserved_usd))
                FILTER (WHERE document_id=%s),0) AS document_usd
        FROM charges""",
        (document_id,),
    ).fetchone()


def admission_error(connection, document_id, amount, global_limit, document_limit):
    """Caller holds the account lock through recording the accepted reservation."""
    amount = Decimal(amount)
    if not amount.is_finite() or amount < 0:
        raise ValueError("The reservation must be finite and nonnegative")
    account = connection.execute(
        "SELECT admission_error FROM summary_budget_account WHERE id=true"
    ).fetchone()
    if account and account["admission_error"]:
        return account["admission_error"]
    used = spending(connection, document_id)
    if used["document_usd"] + amount > Decimal(document_limit):
        return "DOCUMENT_BUDGET"
    if used["spent_usd"] + used["held_usd"] + amount > Decimal(global_limit):
        return "GLOBAL_BUDGET"
    return None


def check_settlement(connection, *, reserved_usd, cost_usd, reserved_input, reported_input):
    """Caller holds the account lock. Pause new calls, never in-flight settlement."""
    cost_exceeded = cost_usd is not None and cost_usd > reserved_usd
    input_exceeded = (
        type(reported_input) is int
        and type(reserved_input) is int
        and reported_input > reserved_input
    )
    if cost_exceeded or input_exceeded:
        connection.execute(
            "UPDATE summary_budget_account SET admission_error='RESERVATION_EXCEEDED' WHERE id=true"
        )
