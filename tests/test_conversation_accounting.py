from decimal import Decimal
from uuid import uuid4

import pytest
from test_conversations import chat_document as chat_document
from test_conversations import start_chat
from test_summaries import summary_document as summary_document

from folio.conversations.invocations import reserve, settle
from folio.conversations.lifecycle import claim_turn
from folio.conversations.memory.context import prepare_pending
from folio.database import Database


@pytest.fixture
def reserved_turn(chat_document):
    settings, client, indexes = chat_document
    chat = start_chat(client, indexes[0])
    submitted = client.post(
        f"/conversations/{chat['id']}/turns",
        json={"question": "When does it begin?"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert submitted.status_code == 202
    database = Database(settings.database_url)
    database.open()
    try:
        turn_id = submitted.json()["id"]
        assert prepare_pending(database, turn_id) is None
        claim = claim_turn(database, turn_id)
        reserve(database, claim, "answer", Decimal("0.04"), 1000, {})
        yield database, client, claim
    finally:
        database.close()


@pytest.mark.integration
@pytest.mark.parametrize("basis,state", [("token_estimate", "estimated"), (None, "known")])
def test_settled_charge_preserves_its_amount_and_basis(reserved_turn, basis, state):
    database, client, claim = reserved_turn
    metadata = {"cost_basis": basis, "prompt_tokens": 100} if basis else {"prompt_tokens": 100}
    assert settle(database, claim, "answer", cost=Decimal("0.01"), metadata=metadata)
    assert settle(database, claim, "answer", cost=Decimal("0.02"))

    trace = client.get(f"/development/conversation-turns/{claim['id']}").json()
    charge = trace["invocations"][0]
    assert charge["billing_state"] == state
    assert Decimal(str(charge["cost_usd"])) == Decimal("0.01")
    assert charge["metadata"].get("cost_basis") == basis
    runtime = client.get("/development/settings").json()["runtime"]
    assert Decimal(runtime["spent_usd"]) == Decimal("0.01")
    assert Decimal(runtime["held_usd"]) == 0


@pytest.mark.integration
def test_late_estimate_releases_unknown_hold_without_publishing(reserved_turn):
    database, client, claim = reserved_turn
    assert settle(database, claim, "answer")
    runtime = client.get("/development/settings").json()["runtime"]
    assert Decimal(runtime["spent_usd"]) == 0
    assert Decimal(runtime["held_usd"]) == Decimal("0.04")

    with database.transaction() as conn:
        conn.execute(
            "UPDATE conversation_turns SET lease_expires_at=now()-interval '1 second' WHERE id=%s",
            (claim["id"],),
        )
    assert not settle(
        database,
        claim,
        "answer",
        cost=Decimal("0.01"),
        metadata={"cost_basis": "token_estimate", "prompt_tokens": 100},
        answer={"outcome": "answer", "statements": [{"text": "A stale answer.", "source_ids": []}]},
    )
    trace = client.get(f"/development/conversation-turns/{claim['id']}").json()
    assert trace["turn"]["answer"] is None
    assert trace["invocations"][0]["billing_state"] == "estimated"
    runtime = client.get("/development/settings").json()["runtime"]
    assert Decimal(runtime["spent_usd"]) == Decimal("0.01")
    assert Decimal(runtime["held_usd"]) == 0
