import argparse
import logging

from folio.config import Settings
from folio.observability import configure_logging


def main():
    parser = argparse.ArgumentParser(prog="folio")
    parser.add_argument("command", choices=["migrate", "dispatch", "worker"])
    parser.add_argument("--burst", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    logging.basicConfig(level=logging.INFO)
    if args.command == "migrate":
        from folio.database import migrate

        migrate(settings.database_url)
    elif args.command == "dispatch":
        from folio.ingestion.dispatcher import run

        run()
    else:
        from rq.serializers import JSONSerializer
        from rq.worker import SpawnWorker

        from folio.ingestion.dispatcher import queue_for

        configure_logging("worker")
        queue = queue_for(settings)
        SpawnWorker(
            [queue],
            connection=queue.connection,
            serializer=JSONSerializer,
            job_monitoring_interval=settings.worker_monitor_seconds,
            log_job_description=False,
        ).work(burst=args.burst)


if __name__ == "__main__":
    main()
