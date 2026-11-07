"""Exercise the running local API with the repository's synthetic PDFs."""

import argparse
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--url", default="http://127.0.0.1:8000")
    args = cli.parse_args()
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    with httpx.Client(base_url=args.url, timeout=20) as client:
        requests = {}
        for name in ("text.pdf", "table.pdf", "mixed.pdf", "damaged.pdf", "encrypted.pdf"):
            content = (fixtures / name).read_bytes()
            headers = {"Idempotency-Key": str(uuid4())}
            response = client.post(
                "/documents", headers=headers, files={"file": (name, content, "application/pdf")}
            )
            response.raise_for_status()
            receipt = response.json()
            replay = client.post(
                "/documents", headers=headers, files={"file": (name, content, "application/pdf")}
            )
            assert replay.json() == receipt
            assert client.get(f"/documents/{receipt['document_id']}/original").content == content
            requests[name] = receipt
            print(f"Accepted {name}: {receipt['request_id']}", flush=True)
        deadline = time.monotonic() + 300
        while requests and time.monotonic() < deadline:
            for name, receipt in list(requests.items()):
                status = client.get(receipt["status_url"]).json()
                if status["state"] == "open":
                    continue
                if name == "encrypted.pdf":
                    assert status["state"] == "failed", status
                    assert status["attempts"][0]["error_code"] == "ENCRYPTED_PDF", status
                else:
                    assert status["state"] == "succeeded", status
                    evidence = client.get(f"/revisions/{status['revision_id']}/evidence").json()
                    text = "\n".join(item["text"] or "" for item in evidence["elements"])
                    if name == "text.pdf":
                        assert "125,000" in text
                    elif name == "table.pdf":
                        table = next(
                            item
                            for item in evidence["elements"]
                            if item["kind"] == "table" and item["locations"][0]["page_no"] == 2
                        )
                        cells = {
                            (cell["row"], cell["column"]): cell["text"]
                            for cell in table["table_data"]["cells"]
                        }
                        assert [cells[1, col] for col in range(3)] == ["Operations", "14", "19"]
                    elif name == "mixed.pdf":
                        assert "30 September 2027" in text
                        assert evidence["pages"][2]["content_observation"] == "no_content_recovered"
                    elif name == "damaged.pdf":
                        assert "CEDAR-17" in text and "MAPLE-42" in text
                        assert evidence["pages"][1]["content_observation"] == "no_content_recovered"
                print(
                    f"Verified {name}: {status['state']}; attempts={len(status['attempts'])}",
                    flush=True,
                )
                del requests[name]
            if requests:
                time.sleep(2)
        assert not requests, f"Timed out waiting for {list(requests)}"


if __name__ == "__main__":
    main()
