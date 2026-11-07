"""Local-only fault exercise: interrupts Folio's own Docker services and restores them."""

import subprocess
import time
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]


def compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, capture_output=True)


def upload(client, name):
    response = client.post(
        "/documents",
        headers={"Idempotency-Key": str(uuid4())},
        files={"file": (name, (ROOT / "tests" / "fixtures" / name).read_bytes())},
    )
    response.raise_for_status()
    return response.json()


def wait_for(client, receipt, predicate, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get(receipt["status_url"]).json()
        if predicate(status):
            return status
        time.sleep(0.3)
    raise AssertionError(f"Timed out: {status}")


def main():
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=20) as client:
        try:
            compose("stop", "redis")
            first, second = upload(client, "text.pdf"), upload(client, "table.pdf")
            pending = wait_for(
                client, first, lambda s: bool(s["attempts"][0]["dispatch_error"]), 45
            )
            assert pending["state"] == "open" and len(pending["attempts"]) == 1
            print("Accepted work stayed pending while Redis was unavailable.", flush=True)
            compose("start", "redis")
            compose("up", "-d", "--scale", "worker=2", "worker")
            outcomes = [
                wait_for(client, receipt, lambda s: s["state"] != "open")
                for receipt in (first, second)
            ]
            assert all(s["state"] == "succeeded" and len(s["attempts"]) == 1 for s in outcomes)
            starts = [datetime.fromisoformat(s["attempts"][0]["started_at"]) for s in outcomes]
            ends = [datetime.fromisoformat(s["attempts"][0]["finished_at"]) for s in outcomes]
            assert max(starts) < min(ends), "Expected overlapping execution on two workers"
            print("Both queued PDFs completed with overlapping worker execution.", flush=True)

            receipt = upload(client, "table.pdf")
            running = wait_for(client, receipt, lambda s: s["attempts"][0]["state"] == "running")
            compose("kill", "-s", "SIGKILL", "worker")
            attempt_id = str(UUID(running["attempts"][0]["id"]))
            # Advance only this synthetic attempt's lease, without waiting seven minutes.
            compose(
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "folio",
                "-d",
                "folio",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "UPDATE processing_attempts SET lease_expires_at=now()-interval '1 second' "
                f"WHERE id='{attempt_id}'",
            )
            compose("up", "-d", "--scale", "worker=2", "worker")
            recovered = wait_for(client, receipt, lambda s: s["state"] != "open")
            assert recovered["state"] == "succeeded", recovered
            assert [a["state"] for a in recovered["attempts"]] == ["failed", "succeeded"]
            assert recovered["attempts"][0]["error_code"] == "WORKER_LOST"
            print(
                "Killed worker recovered once after controlled lease expiry; evidence published.",
                flush=True,
            )
        finally:
            compose("start", "redis")
            compose("up", "-d", "--scale", "worker=1", "worker")


if __name__ == "__main__":
    main()
