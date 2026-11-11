import os
from functools import lru_cache

import psycopg
import pytest

from folio.database import migrate


@lru_cache
def schema():
    url = os.environ.get("FOLIO_DATABASE_URL", "")
    if not url.endswith("/folio_test"):
        pytest.fail("Use a dedicated database ending /folio_test; see docs/development.md")
    migrate(url)


@pytest.fixture(autouse=True)
def integration_schema(request):
    if request.node.get_closest_marker("integration"):
        schema()
        with psycopg.connect(os.environ["FOLIO_DATABASE_URL"]) as connection:
            connection.execute("TRUNCATE documents CASCADE")
            connection.execute("TRUNCATE runtime_configuration")
