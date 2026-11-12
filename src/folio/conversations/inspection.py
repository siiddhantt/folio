from .queries import evidence, turn


def inspect_turn(database, turn_id):
    with database.transaction() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        saved = turn(conn, turn_id)
        if saved is None:
            return None
        run = conn.execute(
            "SELECT policy,input_manifest,available_at,lease_expires_at,dispatch_error "
            "FROM conversation_turns WHERE id=%s",
            (turn_id,),
        ).fetchone()
        attempts = conn.execute(
            "SELECT id,attempt_no,started_at,finished_at,error_code,failure_diagnostics "
            "FROM turn_attempts WHERE turn_id=%s ORDER BY attempt_no",
            (turn_id,),
        ).fetchall()
        invocations = conn.execute(
            "SELECT id,attempt_id,stage,reserved_usd,reserved_input,cost_usd,"
            "billing_state,metadata,invoked_at,finished_at "
            "FROM turn_invocations WHERE turn_id=%s ORDER BY invoked_at,id",
            (turn_id,),
        ).fetchall()
        return {
            "turn": saved,
            **run,
            "attempts": attempts,
            "invocations": invocations,
            "evidence": [
                {k: v for k, v in p.items() if k != "text"} for p in evidence(conn, turn_id)
            ],
        }
