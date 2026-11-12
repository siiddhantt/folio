# Local development and verification

The [README](../README.md) starts the application. The initial parser image uses the
same pinned Docling/CPU/model configuration as the inspected extraction comparison.
The API image contains no Docling runtime. Builds do not receive the local API key;
only the running worker receives it for summaries and embeddings when configured.
The PostgreSQL image adds pinned pgvector 0.8.7 to the existing PostgreSQL 18 base.

## Read the slice

[`api.py`](../src/folio/api.py) assembles the application. Follow one upload through
`routes.py` → `acceptance.py` → `dispatcher.py` → `processing.py`
→ `publication.py` → `queries.py` under [`ingestion/`](../src/folio/ingestion).
[`ownership.py`](../src/folio/ingestion/ownership.py) holds claim rules;
[`recovery.py`](../src/folio/ingestion/recovery.py) records failure and authorizes bounded retries.
The [walkthrough](system-design-walkthrough.md) explains these decisions in plain language.

For indexing, follow the publication intent through
[`indexing/dispatcher.py`](../src/folio/indexing/dispatcher.py) →
[`processing.py`](../src/folio/indexing/processing.py) →
[`lifecycle.py`](../src/folio/indexing/lifecycle.py). Preparation freezes source-linked
chunks; each delivery embeds one bounded batch, and the final transaction exposes
the complete index. [`ai/budget.py`](../src/folio/ai/budget.py) shares admission with
summaries. The [indexing walkthrough](indexing.md) explains recovery and source
reading order. Search and answer generation remain later work.

Keep files together by the behavior they own. Ingestion includes its HTTP routes,
read queries, worker lifecycle, event history and parser. Configuration, database
connections, artifact storage, generic logging and migrations remain shared.
`folio.processing.process_attempt` is a stable queue entry for already-persisted
RQ messages; the implementation lives in `ingestion/processing.py`. Do not remove
that import path while queued deliveries may still reference it.

SQL is explicit here because transaction scope, row locks and ownership conditions are part
of the behavior being reviewed. `Database.transaction()` owns connection/transaction lifetime;
it does not hide those conditions. Versioned SQL migrations run once under a database lock.
Future schema changes get a new migration rather than changing an already-applied file.

## Checks

Install the small development environment with `uv sync --locked`. Start the separate
verification database/broker; they use localhost ports 55432 and 56379:

```sh
docker compose -p folio-check -f compose.test.yaml up -d --build --wait
docker build --target verification -t folio-verification:local -f docker/worker.Dockerfile .
docker run --rm --network folio-check_default --cpus 4 --memory 6g --memory-swap 6g -e FOLIO_DATABASE_URL=postgresql://folio:folio@postgres:5432/folio_test -e FOLIO_REDIS_URL=redis://redis:6379/15 folio-verification:local python -m pytest -m "not supervision" -q
```

Tests reset only the explicitly selected `folio_test` database between persistence tests.
Do not point them at application data. Parser tests use committed synthetic inputs and bundled
models; no inference calls or network model downloads are involved. The isolated test network
still permits PostgreSQL/Redis communication.

The build flag ensures verification PostgreSQL includes pgvector before migration
008 runs. Indexing checks use real isolated PostgreSQL/Redis and controlled
embedding responses; they make no paid model calls. The worker image caches
`cl100k_base` during its build so chunk counting runs offline.

For fast tests on the host, set `FOLIO_DATABASE_URL` to
`postgresql://folio:folio@127.0.0.1:55432/folio_test` and `FOLIO_REDIS_URL` to
`redis://127.0.0.1:56379/15`, then run `uv run pytest -m "not parser and not supervision" -q`.
Use process-local variables rather than replacing application configuration in `.env`.

For host-side DeepSeek counting, install the verified tokenizer assets once with
`PYTHONPATH=src uv run python -m folio.ai.deepseek` (PowerShell:
`$env:PYTHONPATH='src'; uv run python -m folio.ai.deepseek`). This downloads the
pinned tokenizer JSON and MIT license into ignored `.local/tokenizers`; it makes
no inference call. Docker builds do this separately. Runtime counting is offline.

```sh
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run python scripts/smoke.py
```

`smoke.py` exercises the running HTTP application, actual queue/worker/parser and stored
evidence. It verifies text, table relationships, OCR, damaged-page neighbors, encrypted-input
failure, upload replay and original-byte retrieval. It adds synthetic documents to local storage.

## Browser workflow

The [interface walkthrough](interface-walkthrough.md) follows an actual upload through
the browser and persisted processing history. The built web service is at port 3000.
Its `/api` proxy reaches FastAPI; browser document routes do not collide with API routes.

For frontend edits, use Node 22.12 or newer and run these commands from `web`:

```sh
npm ci --ignore-scripts
npm run dev
```

Vite serves port 5173 and proxies `/api` to the local API using `FOLIO_PORT` from
the environment or root `.env` (default 8000). These server settings are not injected
into the browser bundle. It adds no
second application backend. Built assets and self-hosted fonts are served by the
pinned Nginx container in Compose. Font licenses are included under `/licenses/`.

```sh
npm run check
npm run format:check
npm run build
npx playwright install chromium
npm test
```

Browser checks use actual HTTP/queue/parser processing, add synthetic documents to
the selected local instance and do not reset its database. Enable development mode
when running the inspection check. The default test runner starts Vite; set
`FOLIO_E2E_BASE_URL=http://127.0.0.1:3000` to check the built Docker interface instead.
For filtered tests on PowerShell, use
`node node_modules/@playwright/test/cli.js test --grep 'upload a PDF'`.
Playwright retains traces/screenshots on failure in ignored local output folders.

## Fault exercises

Run `uv run python scripts/check_recovery.py` only against this local Compose stack, with no
other processing in progress. It intentionally stops Redis and kills Folio's worker containers.
It restores Redis and one worker in `finally`, but interrupted execution may require
`docker compose up -d --scale worker=1` manually.

The exercise accepts work during a broker outage, restarts transport, observes overlapping
processing by two workers, kills an active worker, and verifies recovery. It advances only its
synthetic attempt's lease in PostgreSQL instead of waiting seven minutes; this is controlled
fault injection, not a measured seven-minute recovery time or a load test.

The optional `supervision` test separately exercises RQ's native-hang hard-stop behavior:

```sh
docker run --rm --init --network folio-check_default --cpus 1 --memory 512m --memory-swap 512m -e FOLIO_RUN_SUPERVISION=1 -e FOLIO_SUPERVISION_REDIS_URL=redis://redis:6379/15 --entrypoint timeout folio-verification:local --signal=TERM --kill-after=5s 100s python tests/test_supervision.py
```

It takes roughly a minute, uses a unique queue, and checks that the workhorse and its
same-group descendant do not survive termination. It does not replace Folio's ownership/retry
checks or guarantee cleanup of descendants that deliberately detach into another process group.
The 1-second job timeout exercises RQ's approximately 60-second parent allowance, not a
promise that jobs always stop at their nominal timeout. Upstream deprecation warnings remain
visible in the checks; they are not suppressed or represented as test failures.

## Boundaries and operations

- Disable automatic summaries in the development console before browser/upload
  smoke checks against an initialized local stack. `FOLIO_SUMMARY_ENABLED=false`
  only seeds a fresh settings record; it does not override saved controls.
  Leave generation enabled only when uploads are deliberately budgeted live
  evaluations. The summary integration tests inject controlled provider responses;
  browser summary tests substitute the summary endpoint, not the server's worker.
- Set `FOLIO_INDEX_ENABLED=false` and recreate the relevant services before
  unbudgeted upload smoke checks. Indexing is environment-managed and independent
  of the saved summary switch; the console does not toggle it. Existing intents
  keep their captured policy. Use the isolated verification stack and controlled
  model responses for indexing fault checks. A ready index is not evidence of
  retrieval or answer quality.
- One worker is the default; `docker compose up -d --scale worker=2 worker` runs two on
  the same host. Each has a 4-CPU/6-GiB ceiling, so check host capacity before increasing count.
- PostgreSQL is the durable work authority. Redis AOF improves persistence but is not an
  atomic extension of a database transaction. Queue delivery can repeat; publication is guarded.
- Health currently checks the API/database path. Pending attempts expose delivery errors;
  that health route alone does not prove a worker is available.
- Failure artifacts retain parser diagnostics and version information where export succeeds.
  If diagnostic storage itself fails, the known error is still recorded; logs identify the lost export.
- Files and rows have separate commits. Ambiguous acceptance errors retain the original.
  Abandoned artifacts are not deleted online. Reconcile only with all artifact writers stopped
  and PostgreSQL recovered, including references from originals, revisions and failed attempts.
- `docker compose down` preserves named volumes. Removing volumes destroys local data;
  it is not part of normal restart or verification instructions.
- Multi-host workers require shared object storage, access control, connection/admission budgets
  and backup/retention decisions. No claim of production readiness or general OCR accuracy follows
  from small synthetic documents or two overlapping workers.

Dependency changes use `uv lock`, followed by `uv export --no-dev --no-emit-project -o requirements.lock`
and `uv export --no-emit-project -o requirements-dev.lock`. Commit the lock/export files together.
Parser changes also require an intentional update of its pinned image, assets and source version.
