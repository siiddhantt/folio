from folio.summaries.preparation import coverage


def conversation(connection, conversation_id):
    return connection.execute(
        """SELECT c.id,c.index_id,c.created_at,i.document_id,i.revision_id,
        COALESCE(c.title,left(t.question,60),left(d.display_name,60)) AS title,
        c.title_source,c.title_version,
        d.display_name AS document_name,t.question,COALESCE(last.state,'empty') AS state,
        COALESCE(last.sequence,0) AS head_sequence,NULL AS max_turns
        FROM conversations c JOIN document_indexes i ON i.id=c.index_id
        JOIN documents d ON d.id=i.document_id
        LEFT JOIN conversation_turns t ON t.conversation_id=c.id AND t.sequence=1
        LEFT JOIN LATERAL (SELECT sequence,state FROM conversation_turns
          WHERE conversation_id=c.id ORDER BY sequence DESC LIMIT 1) last ON true
        WHERE c.id=%s AND c.deleted_at IS NULL""",
        (conversation_id,),
    ).fetchone()


def evidence(connection, turn_id):
    return connection.execute(
        """SELECT e.label AS source_id,e.chunk_ordinal,c.text,e.rank,e.distance,
        array_agg(DISTINCT l.page_no ORDER BY l.page_no) AS pages
        FROM turn_evidence e JOIN index_chunks c
          ON c.index_id=e.index_id AND c.ordinal=e.chunk_ordinal
        JOIN chunk_sources s ON s.index_id=c.index_id AND s.chunk_ordinal=c.ordinal
        JOIN element_locations l ON l.revision_id=s.revision_id AND l.element_id=s.element_id
        WHERE e.turn_id=%s GROUP BY e.label,e.chunk_ordinal,c.text,e.rank,e.distance
        ORDER BY e.rank""",
        (turn_id,),
    ).fetchall()


def turn(connection, turn_id):
    row = connection.execute(
        """SELECT t.id,t.conversation_id,t.sequence,t.parent_sequence,t.question,
        t.resolution->>'query' AS resolved_question,t.state,t.result AS answer,
        CASE WHEN t.state='pending' AND t.memory_dependency_id IS NOT NULL
          AND t.context_snapshot IS NULL THEN 'preparing' END AS context_state,
        t.created_at,t.started_at,t.finished_at,t.error_code,i.revision_id,r.diagnostics
        FROM conversation_turns t JOIN conversations c ON c.id=t.conversation_id
        JOIN document_indexes i ON i.id=t.index_id
        JOIN extraction_revisions r ON r.id=i.revision_id
        WHERE t.id=%s AND c.deleted_at IS NULL""",
        (turn_id,),
    ).fetchone()
    if row is None:
        return None
    row["coverage"] = coverage(
        connection, {"id": row.pop("revision_id"), "diagnostics": row.pop("diagnostics")}
    )
    code = row.pop("error_code")
    row["error"] = {"code": code, "message": error_message(code)} if code else None
    cited = {
        label
        for statement in (row["answer"] or {}).get("statements", [])
        for label in statement["source_ids"]
    }
    row["citations"] = [
        {k: v for k, v in e.items() if k not in {"rank", "distance"}}
        for e in evidence(connection, turn_id)
        if e["source_id"] in cited
    ]
    return row


def error_message(code):
    if code == "CHAT_CONTEXT_WAIT_EXPIRED":
        return "Preparing this chat's context took too long. Your messages are saved."
    if code == "CHAT_CONTEXT_PREPARATION_FAILED":
        return "Older messages could not be summarized safely. Your messages are saved."
    if code == "CHAT_HISTORY_LIMIT":
        return (
            "This chat's history exceeds the current context limit. Start a new chat to continue."
        )
    if "BUDGET" in code or "RESERVATION_EXCEEDED" in code:
        return "This answer could not start within the current AI allowance. Check settings."
    if "INPUT_LIMIT" in code or "CONTEXT_LIMIT" in code:
        return "The prepared question, context and evidence do not fit this answer's input limit."
    if "NOT_CONFIGURED" in code:
        return "An AI provider credential is not configured."
    if "OUTPUT" in code:
        return "The model did not return a complete answer with valid source references."
    return "The answer could not be completed. Your question and document are saved."
