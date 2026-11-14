# Development

Use Docker Compose for the complete application. Host checks need Python 3.12 and
[uv](https://docs.astral.sh/uv/); frontend edits need Node 22.12 or newer. The [architecture](architecture.md)
explains the runtime and source reading order.

## Start locally

Create an ignored `.env` from [`.env.example`](../.env.example) only if you do not already have one. Preserve
existing settings and credentials. Ingestion needs no inference key; summaries and indexing default to disabled.

```sh
docker build --platform linux/amd64 -t folio-docling:2.148.0 docker/docling
docker compose up --build -d --wait
```

The first parser build downloads model assets. The [base image](../docker/docling/README.md) pins Docling, CPU
dependencies and model revisions; processing then runs offline. The API image has no Docling runtime. PostgreSQL
includes pgvector, and Compose applies migrations before starting the API and workers. The image setup targets
Linux amd64.

Open [Folio](http://localhost:3000) or [OpenAPI](http://localhost:8000/docs). `FOLIO_WEB_PORT` and `FOLIO_PORT`
change those localhost ports. Files and database state live in named Docker volumes. `docker compose down`
preserves them; removing volumes destroys local data and is not part of normal restart or testing.

## Configuration

[`.env.example`](../.env.example) lists supported deployment values without usable credentials. Keep `.env`
private and commentless. Compose forwards selected values; settings for host processes also load `.env`. The
[loaders](../src/folio/config.py) validate bounds before work starts.

| Owner | Settings | When changes apply |
| --- | --- | --- |
| Saved development controls | Upload/page limits, parser timeout, summary enablement and token/reasoning controls | Environment seeds once. Console saves persist in PostgreSQL and apply to new uploads. |
| Environment | Connections, keys, supervision, spending, indexing, model/provider and chat/memory controls | Recreate affected services. Accepted work keeps its captured policy. |
| Versioned source | Prompts, schemas, parser/chunker versions, provider profiles and migrations | Change deliberately with the relevant checks. |

Set `FOLIO_DEVELOPMENT_MODE=true`, recreate services, and open
[development settings](http://localhost:3000/development/settings) to change saved controls. Activity on a
document shows processing attempts and safe failure details. Development mode exposes local tooling; it provides
no authentication. Saved controls still apply when the interface is hidden.

Upload middleware captures one configuration revision before reading multipart content, including processing,
summary and indexing policies. A console change cannot alter an accepted upload. Enabling summaries or indexing
does not backfill old work; reads do not generate. Indexing has no console switch. An explicit first index
request for an older revision uses the current environment policy.

The template's initial limits are 25 MiB and 100 pages. Parser timeout is 240 seconds, RQ job timeout 300,
monitor interval 10 and lease 420. Keep parser timeout below the job timeout, and lease above job timeout + 60
seconds + monitor interval. There are three ingestion attempts with persisted retry delays. See
[Settings](../src/folio/config.py) for the remaining validated bounds; changing parser versions also requires an
image and code update. Old incompatible work fails explicitly.

### Models and paid work

`OPENROUTER_API_KEY` is required for enabled summaries and embeddings, including question embeddings.
`OPENAI_API_KEY` is needed only for stages using direct OpenAI. Compose gives the parser/summary/index worker
only the OpenRouter key; chat and memory workers receive both. Neither key reaches the API, dispatcher or
browser bundle.

| Stage | Selected model and route | Default input/output tokens |
| --- | --- | --- |
| Summary | `deepseek/deepseek-v4.1-flash-1017`, `together` through OpenRouter | 64,000 / 16,384 |
| Document and question embeddings | `openai/text-embedding-3-small`, OpenAI through OpenRouter; 1,536 dimensions | 512-token chunks; batches of up to 32 |
| Answer | `openai/gpt-5.2`, provider `openai` | 16,384 / 4,096 |
| Follow-up interpretation | `openai/gpt-5.2`, provider `openai` | 16,384 / 1,024 |
| Older-history notes | `openai/gpt-5.2`, provider `openai` | 16,384 / 2,048 |

Generation defaults to reasoning `none`. Summary settings are independent of chat. The current summary route
uses Together's standard tier; the earlier Fireworks route remains supported without automatic fallback.
Embedding model, route and dimensions are fixed. Its complete plan defaults to at most 4,096 chunks; oversize
plans fail instead of truncating. See [summary](../src/folio/summaries/config.py),
[index](../src/folio/indexing/config.py), [chat](../src/folio/conversations/config.py) and
[memory](../src/folio/conversations/memory/config.py) settings for exact names and validation.

Answer, rewrite and memory gateways are independent. To use direct OpenAI for all three, keep their
model/provider values above and set:

```dotenv
FOLIO_CHAT_GATEWAY=openai
FOLIO_CHAT_REWRITE_GATEWAY=openai
FOLIO_MEMORY_GATEWAY=openai
```

Set any gateway back to `openrouter` to switch that task back. Then recreate:

```sh
docker compose up -d --no-deps --force-recreate api chat-worker memory-worker
```

Each accepted question freezes endpoints and profile versions; legacy work without a gateway stays on
OpenRouter. Keys load at execution and are not saved in policy. Query embeddings retain the pinned index route
even when generation uses direct OpenAI. The [direct adapter](../src/folio/ai/openai.py) supports the reviewed
GPT-5.2 snapshot `gpt-5.2-2025-12-11`; arbitrary model strings do not establish compatibility. There is no
automatic gateway fallback or hidden client retry.

Memory defaults are a 6,000-token trigger, roughly 3,000-token target and 8,000-token hard history limit,
keeping at least two complete recent exchanges raw. Required preparation waits at most 600 seconds. Require
target < trigger <= hard limit; history also shares the full request input allowance with the question and
evidence. Input, schema, margin and output must fit the verified provider limits.

All paid stages share one persistent deployment/document allowance. The template starts at $1 / $0.40 using the
legacy `FOLIO_SUMMARY_*_BUDGET_USD` names. Restarting or enabling another stage does not reset it. Known costs,
explicit token estimates and unresolved reservations all count. Without a valid reported cost or trustworthy
token estimate, the full hold remains; retries need new admission. These are estimate-based controls, not a
provider-enforced zero-overshoot guarantee. See [accounting](architecture.md#model-calls-and-spending). For
shared accounting changes, migrate first and recreate API, dispatcher, worker, chat-worker and memory-worker
together so every process counts the same charge types.

## Aggregate APIs

Open the Monitoring group in [OpenAPI](http://localhost:8000/docs), or request:

```sh
curl http://localhost:8000/statistics/documents
curl http://localhost:8000/metrics/processing
```

Document statistics count current originals and active extraction pages. State
maps omit zero-count states. `documents_without_extraction` stays separate from
pages with no recovered content; neither a blank-page diagnosis nor complete
extraction can be inferred from those counts. `original_bytes` is not disk usage.

Processing metrics cover all retained jobs and attempts, including removed chats.
An index with four successful embedding batches is one job and four attempts.
`unfinished` includes queued or interrupted attempts; it is not a worker count.
`terminal_errors` groups error codes on failed/unavailable jobs, excluding active
retries. Durations include successful and failed attempts with valid start/end
times, exclude queue wait, and start at invocation for memory. No samples means
null mean/max, not zero. Elapsed time may include detecting a lost worker; it
does not isolate CPU/model time or measure answer accuracy or uptime.

Each request uses one consistent read-only database snapshot. Reads trigger no
work or paid calls. Public API schemas describe existing payloads, with examples
for upload, answers and field values; development inspection remains untyped.

## Backend checks

Integration tests truncate their selected database. Use only the isolated `folio_test` database:
[the fixture](../tests/conftest.py) requires that URL suffix and clears documents, saved controls and budget
state. Never point tests at application data.

```sh
uv sync --locked
docker compose -p folio-check -f compose.test.yaml up -d --build --wait
docker build --target verification -t folio-verification:local -f docker/worker.Dockerfile .
docker run --rm --network folio-check_default --cpus 4 --memory 6g --memory-swap 6g -e FOLIO_DATABASE_URL=postgresql://folio:folio@postgres:5432/folio_test -e FOLIO_REDIS_URL=redis://redis:6379/15 folio-verification:local python -m pytest -m "not supervision" -q
```

Build the parser base first. The test database build includes pgvector. Parser checks use committed synthetic
PDFs and bundled models; model boundaries use controlled responses. They make no paid calls and do not measure
real answer quality.

For faster host checks, use a dedicated shell with process-local test connections:

```sh
FOLIO_DATABASE_URL=postgresql://folio:folio@127.0.0.1:55432/folio_test FOLIO_REDIS_URL=redis://127.0.0.1:56379/15 uv run pytest -m "not parser and not supervision" -q
```

PowerShell uses `$env:FOLIO_DATABASE_URL='postgresql://folio:folio@127.0.0.1:55432/folio_test'` and
`$env:FOLIO_REDIS_URL='redis://127.0.0.1:56379/15'` before the same pytest command. Do not replace application
`.env` values. Host DeepSeek counting needs its verified assets once:
`PYTHONPATH=src uv run python -m folio.ai.deepseek` (PowerShell: set `$env:PYTHONPATH='src'` first). This
downloads tokenizer/license files into ignored `.local/tokenizers` without inference. Docker builds install them
separately.

```sh
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
```

## Frontend checks

Run from `web`: `npm ci --ignore-scripts`, then `npm run dev`. Vite uses port 5173 and proxies `/api` to
`FOLIO_PORT` or 8000; these server settings stay outside the bundle.

Full browser checks need the running Compose stack with `FOLIO_DEVELOPMENT_MODE=true`; recreate services after
changing it. Before unbudgeted uploads, disable saved summaries in the console and set
`FOLIO_INDEX_ENABLED=false`, then recreate relevant services. A summary environment flag does not overwrite
saved controls; a mocked browser endpoint does not stop the real worker. Already accepted work keeps its policy.

```sh
npm run check
npm run format:check
npm run build
npx playwright install chromium
npm test
```

Chat/indexing browser suites mostly mock API responses. Document/configuration/runs and several reading/summary
cases use the running application, add synthetic uploads, and sometimes change then restore saved controls. They
do not reset its database.

Playwright starts/reuses Vite by default. Set `FOLIO_E2E_BASE_URL=http://127.0.0.1:3000` for the built
interface. On PowerShell, filtered runs can use
`node node_modules/@playwright/test/cli.js test --grep 'upload a PDF'`. Failure traces/screenshots stay in
ignored output folders.

## Smoke and fault exercises

`uv run python scripts/smoke.py` exercises real HTTP, queue, parser and saved evidence. It adds synthetic
documents and checks replay, originals, text/tables/OCR, partial results and encrypted-input failure. Use the
paid-work precautions above.

`uv run python scripts/check_recovery.py` stops Redis and kills workers. Run only on an idle local stack.
Cleanup restores Redis and one worker; interruption may need `docker compose up -d --scale worker=1`. It
advances its synthetic lease, so its result is not a measured seven-minute recovery time or a load test.

The optional native-hang probe uses a unique queue and takes roughly a minute:

```sh
docker run --rm --init --network folio-check_default --cpus 1 --memory 512m --memory-swap 512m -e FOLIO_RUN_SUPERVISION=1 -e FOLIO_SUPERVISION_REDIS_URL=redis://redis:6379/15 --entrypoint timeout folio-verification:local --signal=TERM --kill-after=5s 100s python tests/test_supervision.py
```

It checks workhorse/same-group descendant cleanup; detached process groups are outside that guarantee. The
one-second job timeout includes RQ's longer parent allowance. Ownership/retry checks remain separate. Model
quality needs a budgeted [evaluation](evaluation.md).

Dependency changes use `uv lock`, then `uv export --no-dev --no-emit-project -o requirements.lock` and
`uv export --no-emit-project -o requirements-dev.lock`; commit the lock/export files together. Add a new
numbered migration instead of editing an applied one. Parser changes require deliberate image, asset and
source-version updates.
