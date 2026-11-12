from concurrent.futures import ThreadPoolExecutor, TimeoutError
from decimal import Decimal
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_summaries import Model
from test_summaries import summary_document as summary_document

from folio.ai.budget import admission_error, lock_account
from folio.database import Database
from folio.summaries.lifecycle import claim_run, reserve_invocation
from folio.summaries.processing import process_summary


def embedding_charge(connection, receipt, revision_id, *, reserved, cost=None):
    index_id = uuid4()
    row = connection.execute(
        """INSERT INTO document_indexes(id,revision_id,document_id,policy,state)
        VALUES (%s,%s,%s,%s,'pending') ON CONFLICT (revision_id)
        DO UPDATE SET revision_id=EXCLUDED.revision_id RETURNING id""",
        (index_id, revision_id, receipt["document_id"], Jsonb({})),
    ).fetchone()
    index_id = row["id"]
    attempt_id = uuid4()
    connection.execute(
        "INSERT INTO indexing_attempts(id,index_id,attempt_no,token) VALUES (%s,%s,1,%s)",
        (attempt_id, index_id, uuid4()),
    )
    connection.execute(
        """INSERT INTO embedding_invocations
        (id,index_id,attempt_id,reserved_usd,cost_usd,invoked_at,billing_state)
        VALUES (%s,%s,%s,%s,%s,clock_timestamp(),%s)""",
        (uuid4(), index_id, attempt_id, reserved, cost, "known" if cost is not None else "unknown"),
    )


@pytest.mark.integration
@pytest.mark.parametrize("cost", [None, Decimal("0.03")])
def test_embedding_charges_share_summary_allowance_and_console_totals(summary_document, cost):
    settings, client, publish = summary_document
    receipt, revision_id = publish()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        embedding_charge(connection, receipt, revision_id, reserved=Decimal("0.10"), cost=cost)

    model = Model()
    url = f"/revisions/{revision_id}/summary"
    result = process_summary(client.get(url).json()["run_id"], settings=settings, client=model)
    runtime = client.get("/development/settings").json()["runtime"]
    if cost is None:
        assert result == {"outcome": "unavailable", "code": "SUMMARY_DOCUMENT_BUDGET"}
        assert model.calls == []
        assert Decimal(runtime["spent_usd"]) == 0
        assert Decimal(runtime["held_usd"]) == Decimal("0.10")
        assert Decimal(runtime["remaining_usd"]) == Decimal("0.90")
    else:
        assert result == {"outcome": "ready"}
        assert len(model.calls) == 1
        assert Decimal(runtime["spent_usd"]) == Decimal("0.030045")
        assert Decimal(runtime["held_usd"]) == 0
        assert Decimal(runtime["remaining_usd"]) == Decimal("0.969955")


@pytest.mark.integration
def test_embedding_and_summary_admission_cannot_spend_the_same_allowance(
    summary_document, monkeypatch
):
    settings, client, publish = summary_document
    monkeypatch.setenv("FOLIO_SUMMARY_DOCUMENT_BUDGET_USD", "1")
    receipt, revision_id = publish()
    _, summary_revision = publish()
    run_id = client.get(f"/revisions/{summary_revision}/summary").json()["run_id"]
    database = Database(settings.database_url)
    database.open()
    started = Event()
    try:
        claim = claim_run(database, run_id)

        def reserve_summary():
            started.set()
            return reserve_invocation(database, claim, {"reservation_usd": "0.60"})

        with ThreadPoolExecutor(max_workers=1) as workers:
            with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
                allowance = lock_account(connection, "1")
                assert (
                    admission_error(connection, receipt["document_id"], "0.60", allowance, "1")
                    is None
                )
                embedding_charge(connection, receipt, revision_id, reserved=Decimal("0.60"))
                summary = workers.submit(reserve_summary)
                assert started.wait(5)
                # The embedding reservation is still uncommitted. Admission must wait.
                with pytest.raises(TimeoutError):
                    summary.result(timeout=0.2)
            assert summary.result(timeout=5) == "SUMMARY_GLOBAL_BUDGET"
        runtime = client.get("/development/settings").json()["runtime"]
        assert Decimal(runtime["held_usd"]) == Decimal("0.60")
        assert Decimal(runtime["remaining_usd"]) == Decimal("0.40")
    finally:
        database.close()
