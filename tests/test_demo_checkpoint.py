import json
import os

import httpx
import pytest

from notebooks.checkpoint import bind_run, save_json, submit_once


def test_lost_response_replays_original_question_and_head_from_disk(tmp_path):
    accepted = {}
    submitted = []

    def server(request):
        body = json.loads(request.content)
        key = request.headers["Idempotency-Key"]
        submitted.append((key, body))
        if key not in accepted:
            accepted[key] = {"id": "turn-1", "conversation_id": "chat-1"}
            raise httpx.ReadTimeout("Response lost after acceptance", request=request)
        return httpx.Response(202, json=accepted[key])

    path = tmp_path / "question.json"
    identity = {"conversation_id": "chat-1", "question": "What about the table?"}
    with httpx.Client(transport=httpx.MockTransport(server), base_url="http://localhost") as client:

        def submit(head):
            return submit_once(
                path,
                identity=identity,
                prepare=lambda: {"question": identity["question"], "observed_head": head},
                send=lambda body, key: client.post(
                    "/conversations/chat-1/turns",
                    json=body,
                    headers={"Idempotency-Key": key},
                ),
                read_saved=lambda saved: client.get(f"/conversations/chat-1/turns/{saved['id']}"),
            )

        with pytest.raises(httpx.ReadTimeout):
            submit(0)
        # No in-memory checkpoint object survives: load it again as a restarted kernel would.
        receipt = submit(1)

    assert receipt == {"id": "turn-1", "conversation_id": "chat-1"}
    assert len(accepted) == 1
    assert submitted[0] == submitted[1]
    assert submitted[1][1] == {"question": "What about the table?", "observed_head": 0}


def test_changed_question_cannot_reuse_a_saved_intent(tmp_path):
    path = tmp_path / "question.json"
    identity = {"conversation_id": "chat-1", "question": "Original question"}
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(202, json={"id": "turn-1"})),
        base_url="http://localhost",
    ) as client:
        callbacks = {
            "prepare": lambda: {"question": identity["question"], "observed_head": 0},
            "send": lambda body, key: client.post("/turns", json=body),
            "read_saved": lambda saved: client.get(f"/turns/{saved['id']}"),
        }
        submit_once(path, identity=identity, **callbacks)
        with pytest.raises(ValueError, match="identity"):
            submit_once(path, identity=identity | {"question": "Changed question"}, **callbacks)


@pytest.mark.parametrize("changed", [{"api_url": "http://localhost:9000"}, {"sha256": "other"}])
def test_run_rejects_changed_server_or_pdf(tmp_path, changed):
    path = tmp_path / "run.json"
    identity = {"api_url": "http://localhost:8000", "filename": "guide.pdf", "sha256": "first"}
    original = bind_run(path, identity)
    assert bind_run(path, identity) == original
    with pytest.raises(ValueError, match="identity"):
        bind_run(path, identity | changed)


def test_missing_saved_resource_stops_instead_of_submitting_again(tmp_path):
    writes = []

    def server(request):
        if request.method == "POST":
            writes.append(request)
            return httpx.Response(202, json={"id": "turn-1"})
        return httpx.Response(404, json={"detail": "Not found"})

    with httpx.Client(transport=httpx.MockTransport(server), base_url="http://localhost") as client:
        arguments = {
            "identity": {"question": "Original question"},
            "prepare": lambda: {"question": "Original question", "observed_head": 0},
            "send": lambda body, key: client.post("/turns", json=body),
            "read_saved": lambda saved: client.get(f"/turns/{saved['id']}"),
        }
        path = tmp_path / "question.json"
        submit_once(path, **arguments)
        with pytest.raises(httpx.HTTPStatusError) as error:
            submit_once(path, **arguments)
    assert error.value.response.status_code == 404
    assert len(writes) == 1


def test_failed_snapshot_replacement_preserves_previous_checkpoint(tmp_path, monkeypatch):
    path = tmp_path / "run.json"
    save_json(path, {"saved": "previous complete value"})

    def disk_failure(*args):
        raise OSError("Replacement unavailable")

    monkeypatch.setattr(os, "replace", disk_failure)
    with pytest.raises(OSError):
        save_json(path, {"saved": "new value"})
    assert json.loads(path.read_text()) == {"saved": "previous complete value"}


def test_request_is_not_sent_when_intent_cannot_be_saved(tmp_path, monkeypatch):
    def disk_failure(*args):
        raise OSError("Disk unavailable")

    monkeypatch.setattr(os, "replace", disk_failure)
    with pytest.raises(OSError):
        submit_once(
            tmp_path / "question.json",
            identity={"question": "A question"},
            prepare=lambda: {"question": "A question", "observed_head": 0},
            send=lambda body, key: pytest.fail("No durable key: must not send a paid request"),
            read_saved=lambda saved: pytest.fail("No receipt yet"),
        )
