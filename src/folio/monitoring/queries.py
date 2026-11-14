from folio.database import Database
from folio.monitoring.models import StageStatistics


def document_statistics(database: Database) -> dict:
    with database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        result = connection.execute(
            """SELECT CURRENT_TIMESTAMP AS as_of, count(*) AS total_documents,
            coalesce(sum(f.byte_size),0) AS original_bytes
            FROM documents d
            LEFT JOIN ingestion_requests r ON r.id=d.current_request_id
            LEFT JOIN file_versions f ON f.id=r.file_version_id"""
        ).fetchone()
        states = connection.execute(
            """SELECT coalesce(r.state,'not_started') AS extraction,
            coalesce(s.state,'not_scheduled') AS summary,
            coalesce(i.state,'not_started') AS indexing, count(*) AS count
            FROM documents d
            LEFT JOIN ingestion_requests r ON r.id=d.current_request_id
            LEFT JOIN summary_runs s ON s.revision_id=d.active_revision_id
            LEFT JOIN document_indexes i ON i.revision_id=d.active_revision_id
            GROUP BY 1,2,3"""
        ).fetchall()
        for source, field in (
            ("extraction", "extraction_states"),
            ("summary", "summary_states"),
            ("indexing", "index_states"),
        ):
            counts = result[field] = {}
            for row in states:
                counts[row[source]] = counts.get(row[source], 0) + row["count"]
        result["pages"] = connection.execute(
            """SELECT count(p.page_no) AS total,
            count(*) FILTER (WHERE p.content_observation='content_recovered') AS with_content,
            count(*) FILTER (WHERE p.content_observation='no_content_recovered') AS without_content,
            count(*) FILTER (WHERE d.active_revision_id IS NULL) AS documents_without_extraction
            FROM documents d LEFT JOIN source_pages p ON p.revision_id=d.active_revision_id"""
        ).fetchone()
        return result


def processing_metrics(database: Database) -> dict:
    stages = {
        name: StageStatistics().model_dump()
        for name in ("extraction", "summary", "indexing", "chat", "memory")
    }
    with database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        as_of = connection.execute("SELECT CURRENT_TIMESTAMP AS value").fetchone()["value"]
        jobs = connection.execute(
            """WITH jobs AS (
                SELECT 'extraction' AS stage,r.state,a.error_code
                FROM ingestion_requests r
                LEFT JOIN processing_attempts a ON a.id=r.authorized_attempt_id
                UNION ALL SELECT 'summary',state,error_code FROM summary_runs
                UNION ALL SELECT 'indexing',state,error_code FROM document_indexes
                UNION ALL SELECT 'chat',state,error_code FROM conversation_turns
                UNION ALL SELECT 'memory',state,error_code FROM conversation_memories
            ) SELECT stage,state,error_code,count(*) AS count
            FROM jobs GROUP BY stage,state,error_code"""
        ).fetchall()
        for row in jobs:
            stage = stages[row["stage"]]
            stage["jobs"]["total"] += row["count"]
            states = stage["jobs"]["states"]
            states[row["state"]] = states.get(row["state"], 0) + row["count"]
            if row["state"] in ("failed", "unavailable") and row["error_code"]:
                errors = stage["terminal_errors"]
                errors[row["error_code"]] = errors.get(row["error_code"], 0) + row["count"]
        attempts = connection.execute(
            """WITH attempts AS (
                SELECT 'extraction' AS stage,started_at,finished_at,state='failed' AS failed
                FROM processing_attempts
                UNION ALL SELECT 'summary',started_at,finished_at,error_code IS NOT NULL
                FROM summary_attempts
                UNION ALL SELECT 'indexing',started_at,finished_at,state='failed'
                FROM indexing_attempts
                UNION ALL SELECT 'chat',started_at,finished_at,error_code IS NOT NULL
                FROM turn_attempts
                UNION ALL SELECT 'memory',invoked_at,finished_at,error_code IS NOT NULL
                FROM memory_attempts
            ), measured AS (
                SELECT *, CASE WHEN finished_at>=started_at
                THEN extract(epoch FROM finished_at-started_at)::double precision END AS seconds
                FROM attempts
            ) SELECT stage,count(*) AS total,
            count(finished_at) AS completed,
            count(*) FILTER (WHERE finished_at IS NULL) AS unfinished,
            count(*) FILTER (WHERE finished_at IS NOT NULL AND failed) AS failed,
            count(seconds) AS samples,avg(seconds) AS mean,max(seconds) AS max
            FROM measured GROUP BY stage"""
        ).fetchall()
        for row in attempts:
            stage = stages[row.pop("stage")]
            row["duration_seconds"] = {key: row.pop(key) for key in ("samples", "mean", "max")}
            stage["attempts"] = row
    return {"as_of": as_of, "scope": "all_retained", "stages": stages}
