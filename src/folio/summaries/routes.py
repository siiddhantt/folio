from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException

from folio.summaries.preparation import coverage

ERRORS = {
    "SUMMARY_DISABLED": "Automatic summaries are disabled for this document.",
    "SUMMARY_CONFIGURATION_INVALID": "Summary settings are invalid for this document.",
    "INVALID_OUTPUT": "The model did not return a complete summary with valid source references.",
    "SUMMARY_INPUT_LIMIT": "The complete available evidence exceeds this summary's input limit.",
    "SUMMARY_CONTEXT_LIMIT": "The available evidence does not fit the selected model route.",
    "SUMMARY_GLOBAL_BUDGET": "The remaining summary allowance cannot cover this document.",
    "SUMMARY_DOCUMENT_BUDGET": "The summary cannot fit this document's spending limit.",
    "SUMMARY_WORKER_LOST": "Summary processing was interrupted before a result was saved.",
    "SUMMARY_DELIVERY_FAILED": "Summary processing could not start after repeated queue failures.",
    "SUMMARY_PROVIDER_NOT_CONFIGURED": "A summary provider credential is not configured.",
    "SUMMARY_MODEL_UNAVAILABLE": "The configured model route is unavailable or incompatible.",
    "SUMMARY_EXECUTION_CONFIG_MISMATCH": "Summary settings are incompatible with this worker.",
    "SUMMARY_SPECIFICATION_CHANGED": (
        "The saved summary specification no longer matches the model or preparation settings."
    ),
    "SUMMARY_PROVIDER_TIMEOUT": "The summary provider did not respond within the time limit.",
    "SUMMARY_PROVIDER_UNAVAILABLE": "The summary provider is temporarily unavailable.",
    "SUMMARY_PROVIDER_RATE_LIMIT": "The summary provider has temporarily limited requests.",
    "SUMMARY_PROVIDER_REJECTED": "The summary provider rejected the request.",
    "SUMMARY_PROVIDER_RESPONSE_INVALID": "The summary provider returned an unusable response.",
}


def read_summary(database, revision_id):
    with database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        revision = connection.execute(
            "SELECT id,diagnostics FROM extraction_revisions WHERE id=%s", (revision_id,)
        ).fetchone()
        if revision is None:
            return None
        run = connection.execute(
            "SELECT * FROM summary_runs WHERE revision_id=%s", (revision_id,)
        ).fetchone()
        result = (run["result"] or {}) if run else {}
        source_ids = {
            source_id
            for statement in [result.get("overview", {}), *result.get("points", [])]
            for source_id in statement.get("source_ids", [])
        }
        citations = connection.execute(
            """SELECT e.element_id AS source_id,e.text,e.table_data,
            array_agg(DISTINCT l.page_no ORDER BY l.page_no) AS pages
            FROM source_elements e JOIN element_locations l USING(revision_id,element_id)
            WHERE e.revision_id=%s AND e.element_id=ANY(%s)
            GROUP BY e.element_id,e.text,e.table_data,e.reading_order ORDER BY e.reading_order""",
            (revision_id, list(source_ids)),
        ).fetchall()
        attempts = (
            connection.execute(
                "SELECT * FROM summary_attempts WHERE run_id=%s ORDER BY attempt_no", (run["id"],)
            ).fetchall()
            if run
            else []
        )
        known_costs = [
            attempt["cost_usd"] for attempt in attempts if attempt["cost_usd"] is not None
        ]
        uncertain = sum(
            (
                attempt["reserved_usd"]
                for attempt in attempts
                if attempt["billing_state"] in ("reserved", "unknown")
            ),
            Decimal(0),
        )

        def tokens(name):
            values = [
                attempt["usage"].get(name)
                for attempt in attempts
                if attempt["invoked_at"] is not None or attempt["usage"]
            ]
            return sum(values) if values and all(value is not None for value in values) else None

        return {
            "revision_id": str(revision_id),
            "run_id": str(run["id"]) if run else None,
            "state": run["state"] if run else "not_scheduled",
            "overview": result.get("overview"),
            "points": result.get("points", []),
            "citations": citations,
            "coverage": coverage(connection, revision),
            "error": {
                "code": run["error_code"],
                "message": ERRORS.get(run["error_code"], "The summary could not be completed."),
            }
            if run and run["error_code"]
            else None,
            "usage": {
                "attempts": len(attempts),
                "prompt_tokens": tokens("prompt_tokens"),
                "completion_tokens": tokens("completion_tokens"),
                "cost_usd": str(sum(known_costs, Decimal(0)))
                if known_costs and not uncertain
                else None,
                "uncertain_cost_usd": str(uncertain),
            },
            "created_at": run["created_at"] if run else None,
            "finished_at": run["finished_at"] if run else None,
        }


def create_router(database):
    router = APIRouter()

    @router.get("/revisions/{revision_id}/summary")
    def summary(revision_id: UUID):
        value = read_summary(database, revision_id)
        if value is None:
            raise HTTPException(404, "Not found")
        return value

    return router
