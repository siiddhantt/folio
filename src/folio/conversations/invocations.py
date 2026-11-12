"""Paid-stage admission and settlement; no retrieval or prompt decisions."""

import json
from uuid import uuid4

from psycopg.types.json import Jsonb

from folio.ai.budget import admission_error, check_settlement, lock_account

from .lifecycle import owned, transition


class AdmissionError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def reserve(database, claim, stage, amount, input_tokens, metadata):
    with database.transaction() as conn:
        allowance = lock_account(conn, claim["policy"]["budget_usd"])
        if owned(conn, claim) is None:
            raise AdmissionError("CHAT_SUPERSEDED")
        document = conn.execute(
            "SELECT document_id FROM document_indexes WHERE id=%s", (claim["index_id"],)
        ).fetchone()
        code = admission_error(
            conn, document["document_id"], amount, allowance, claim["policy"]["document_budget_usd"]
        )
        if code:
            raise AdmissionError("CHAT_" + code)
        conn.execute(
            "INSERT INTO turn_invocations "
            "(id,turn_id,attempt_id,stage,reserved_usd,reserved_input,metadata) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                uuid4(),
                claim["id"],
                claim["attempt_id"],
                stage,
                amount,
                input_tokens,
                Jsonb(metadata),
            ),
        )


def settle(
    database, claim, stage, *, cost=None, metadata=None, vector=None, answer=None, resolution=None
):
    """A stale worker's charge survives; only the owner can publish a checkpoint."""
    with database.transaction() as conn:
        conn.execute("SELECT id FROM summary_budget_account WHERE id=true FOR UPDATE")
        row = owned(conn, claim)
        charge = conn.execute(
            "UPDATE turn_invocations SET cost_usd=COALESCE(cost_usd,%s),"
            "metadata=CASE WHEN cost_usd IS NULL THEN metadata || jsonb_strip_nulls(%s) "
            "ELSE metadata END,"
            "finished_at=clock_timestamp(),billing_state=CASE WHEN COALESCE(cost_usd,%s) "
            "IS NULL THEN 'unknown' ELSE 'known' END "
            "WHERE turn_id=%s AND attempt_id=%s AND stage=%s RETURNING *",
            (cost, Jsonb(metadata or {}), cost, claim["id"], claim["attempt_id"], stage),
        ).fetchone()
        if charge:
            check_settlement(
                conn,
                reserved_usd=charge["reserved_usd"],
                cost_usd=charge["cost_usd"],
                reserved_input=charge["reserved_input"],
                reported_input=charge["metadata"].get("prompt_tokens"),
            )
        if row is None:
            return False
        if resolution is not None:
            conn.execute(
                "UPDATE conversation_turns SET resolution=%s WHERE id=%s",
                (Jsonb(resolution), claim["id"]),
            )
        if vector is not None:
            conn.execute(
                "UPDATE conversation_turns SET query_vector=%s::vector WHERE id=%s",
                (json.dumps(vector, allow_nan=False), claim["id"]),
            )
        if answer is not None:
            title = answer.get("title")
            if title:
                conn.execute(
                    "UPDATE conversations SET title=%s,title_source='generated' "
                    "WHERE id=%s AND title_source IS DISTINCT FROM 'manual'",
                    (title, row["conversation_id"]),
                )
            answer = {key: value for key, value in answer.items() if key != "title"}
            conn.execute(
                "UPDATE turn_attempts SET finished_at=clock_timestamp() WHERE id=%s",
                (claim["attempt_id"],),
            )
            transition(conn, row, result=answer)
        return True
