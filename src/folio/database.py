from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, url: str):
        self.pool = ConnectionPool(
            url,
            min_size=1,
            max_size=8,
            timeout=10,
            kwargs={
                "row_factory": dict_row,
                "autocommit": True,
                "connect_timeout": 5,
                "options": "-c statement_timeout=15000 -c lock_timeout=5000",
            },
            open=False,
        )

    def open(self):
        try:
            self.pool.open(wait=True, timeout=15)
        except Exception:
            self.pool.close()
            raise

    def close(self):
        self.pool.close()

    @contextmanager
    def transaction(self):
        with self.pool.connection() as connection, connection.transaction():
            yield connection


def migrate(url: str):
    with psycopg.connect(url, connect_timeout=5) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(718402601)")
        connection.execute("CREATE TABLE IF NOT EXISTS schema_versions (version int PRIMARY KEY)")
        for migration in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
            version = int(migration.stem.split("_")[0])
            if not connection.execute(
                "SELECT 1 FROM schema_versions WHERE version = %s", (version,)
            ).fetchone():
                connection.execute(migration.read_text(encoding="utf-8"))
                connection.execute("INSERT INTO schema_versions VALUES (%s)", (version,))
