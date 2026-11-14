"""Development-only summary execution facts, without prompts or generated text."""

SAFE_USAGE = (
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "finish_reason",
    "response_characters",
    "model",
    "provider",
)


def inspect_summary(connection, request_id):
    run = connection.execute(
        """SELECT s.id,s.state,s.created_at,s.started_at,s.finished_at,s.error_code
        FROM summary_runs s JOIN extraction_revisions r ON r.id=s.revision_id
        WHERE r.request_id=%s""",
        (request_id,),
    ).fetchone()
    if run is None:
        return None
    run["attempts"] = connection.execute(
        """SELECT id,attempt_no,started_at,finished_at,invoked_at,error_code,response_id,
        billing_state,reserved_usd,cost_usd,usage,failure_diagnostics,
        CASE WHEN finished_at IS NULL THEN 'running'
             WHEN error_code IS NOT NULL THEN 'failed' ELSE 'succeeded' END AS state
        FROM summary_attempts WHERE run_id=%s ORDER BY attempt_no""",
        (run["id"],),
    ).fetchall()
    for attempt in run["attempts"]:
        usage = attempt["usage"]
        attempt["usage"] = {key: usage[key] for key in SAFE_USAGE if key in usage}
    return run
