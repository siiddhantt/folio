"""Opt-in Linux/container check of RQ's native-job hard stop (about one minute).

Use a disposable container with --init and an outer timeout. Set
FOLIO_RUN_SUPERVISION=1 and FOLIO_SUPERVISION_REDIS_URL to the dedicated Redis DB15.
This can also run directly with unittest in the production worker image.
"""

import json
import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from redis import Redis
from rq import Queue, Worker
from rq.job import JobStatus
from rq.serializers import JSONSerializer

try:
    import pytest
except ImportError:
    pytestmark = []  # unittest can run this without installing pytest in production.
else:
    pytestmark = pytest.mark.supervision


@unittest.skipUnless(os.environ.get("FOLIO_RUN_SUPERVISION") == "1", "explicit opt-in required")
class NativeSupervision(unittest.TestCase):
    def test_parent_kills_native_job_and_its_process_group(self):
        redis_url = os.environ["FOLIO_SUPERVISION_REDIS_URL"]
        self.assertEqual(urlparse(redis_url).path, "/15", "Use the isolated test Redis DB15")
        self.assertEqual(sys.platform, "linux", "Run inside the Linux worker container")
        connection = Redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
        token = f"folio-supervision-{uuid4().hex}"
        probe_key = f"{token}:probe"
        worker_name = f"{token}-worker"
        queue = Queue(token, connection=connection, serializer=JSONSerializer)
        job = queue.enqueue(
            "worker_faults.native_block",
            redis_url,
            probe_key,
            job_id=f"{token}-job",
            job_timeout=1,
            result_ttl=120,
            failure_ttl=120,
        )
        worker = None
        probe = None
        try:
            worker = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).with_name("worker_faults.py")),
                    redis_url,
                    token,
                    worker_name,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            output, _ = worker.communicate(timeout=85)
            self.assertEqual(worker.returncode, 0, output)
            raw_probe = connection.get(probe_key)
            self.assertIsNotNone(raw_probe, output)
            probe = json.loads(raw_probe)
            elapsed = time.monotonic() - probe["started_monotonic"]
            job.refresh()
            self.assertEqual(job.get_status(), JobStatus.FAILED, output)
            self.assertIn(job.id, queue.failed_job_registry.get_job_ids())
            result = job.latest_result()
            self.assertIsNotNone(result)
            # RQ 3.0 discards waitpid's return in this timeout branch, so its
            # failure text cannot reliably report the terminating signal.
            self.assertIn("Work-horse terminated unexpectedly", result.exc_string)
            kill_message = f"killed horse pid {probe['horse_pid']}"
            self.assertIn(kill_message, output)
            self.assertGreaterEqual(elapsed, 60, "Must exercise the parent hard-stop path")
            self.assertLess(elapsed, 85)
            self.assertEqual(probe["process_group"], probe["horse_pid"])
            self.assertEqual(probe["descendant_group"], probe["process_group"])
            deadline = time.monotonic() + 5
            pids = [probe["horse_pid"], probe["descendant_pid"]]
            while (
                any(Path(f"/proc/{pid}").exists() for pid in pids) and time.monotonic() < deadline
            ):
                time.sleep(0.05)
            self.assertTrue(all(not Path(f"/proc/{pid}").exists() for pid in pids), probe)
            print(
                json.dumps(
                    {
                        "elapsed_seconds": round(elapsed, 3),
                        "job_status": "failed",
                        "failure": result.exc_string,
                        "parent_kill_log": kill_message,
                        "probe": probe,
                        "horse_and_descendant_gone": True,
                    }
                ),
                flush=True,
            )
        finally:
            if worker is not None and worker.poll() is None:
                worker.kill()
                worker.wait(timeout=5)
            if probe is None:
                raw_probe = connection.get(probe_key)
                probe = json.loads(raw_probe) if raw_probe else None
            if probe and probe["process_group"] == probe["horse_pid"]:
                try:
                    os.killpg(probe["process_group"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
            registered = Worker.find_by_key(f"rq:worker:{worker_name}", connection=connection)
            if registered is not None:
                registered.register_death()
            job.delete()
            queue.delete()
            # Only this run's unguessable token; never flush a shared Redis database.
            keys = list(connection.scan_iter(match=f"*{token}*"))
            if keys:
                connection.delete(*keys)
            connection.close()


if __name__ == "__main__":
    unittest.main()
