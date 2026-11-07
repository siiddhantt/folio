"""Explicitly invoked, bounded-container faults for the worker supervision check."""

import hashlib
import json
import os
import subprocess
import sys
import time

from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer
from rq.worker import SpawnWorker


def native_block(redis_url: str, probe_key: str):
    """Delay Python signal handling in OpenSSL; the worker parent must kill us."""
    descendant = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
    connection = Redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
    connection.set(
        probe_key,
        json.dumps(
            {
                "horse_pid": os.getpid(),
                "process_group": os.getpgrp(),
                "descendant_pid": descendant.pid,
                "descendant_group": os.getpgid(descendant.pid),
                "started_monotonic": time.monotonic(),
            }
        ),
        ex=180,
    )
    # This call runs in native code and does not periodically execute Python's
    # pending SIGALRM handler. The disposable container supplies an outer bound.
    hashlib.pbkdf2_hmac("sha256", b"synthetic-test-input", b"synthetic-salt", 2_147_483_647)
    return "unexpected native completion"


if __name__ == "__main__":
    redis_url, queue_name, worker_name = sys.argv[1:]
    connection = Redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
    queue = Queue(queue_name, connection=connection, serializer=JSONSerializer)
    worker = SpawnWorker(
        [queue],
        connection=connection,
        serializer=JSONSerializer,
        name=worker_name,
        job_monitoring_interval=1,
    )
    worker.work(burst=True, max_jobs=1, with_scheduler=False)
