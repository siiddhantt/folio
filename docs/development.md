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
includes pgvector, and Compose applies migrations before starting the API and workers. The default setup
targets Linux amd64; Apple Silicon uses the worker override below.

Open [Folio](http://localhost:3000) or [OpenAPI](http://localhost:8000/docs). `FOLIO_WEB_PORT` and `FOLIO_PORT`
change those localhost ports. Files and database state live in named Docker volumes. `docker compose down`
preserves them; removing volumes destroys local data and is not part of normal restart or testing.

## Running on a Mac

Intel Macs use the commands above. On Apple Silicon, set this value in the
existing private `.env` (replace an existing `COMPOSE_FILE` value rather than
adding a duplicate):

```dotenv
COMPOSE_FILE=compose.yaml:compose.arm64.yaml
```

Then build the native document worker's base and start normally:

```sh
docker build --platform linux/arm64 -t folio-docling:2.148.0-arm64 docker/docling
docker compose up --build -d --wait
docker compose exec worker python -c 'import platform; print(platform.machine())'
```

The last command should print `aarch64`. The overlay changes only the document
worker, including local parsing, chunk preparation and its existing summary/index
jobs. It uses the same application code, parser versions and model assets. Other
services remain amd64; PostgreSQL still pins an amd64 pgvector package. Databases,
uploaded files and existing extraction records stay in the same named volumes.
The ARM64 worker uses CPU inference; this does not enable the Mac GPU.

To switch an already running, idle stack, use `docker compose up --build -d --no-deps worker`
after building the base. Let active work finish first. To return to the original
worker, set `COMPOSE_FILE=compose.yaml` and run
`docker compose -f compose.yaml up --build -d --no-deps worker`
with the original amd64 base available. This changes the worker for subsequent
work; it does not re-extract existing partial documents. Upload again to create a
new result. Saved parser/job/lease limits continue to apply.

On Apple Silicon, Docker Desktop's Apple Virtualization framework supports optional Rosetta
acceleration. Docker VMM currently does not support Rosetta and documents slower amd64 emulation.
See Docker's [VM choices](https://docs.docker.com/desktop/features/vmm/) and
[settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/).
The default VM memory allocation is half the Mac's RAM. Leave room for macOS and check the
allocation before parsing: Folio's document worker can use up to 6 GiB, with other services
using additional memory. That is a ceiling, not memory reserved at startup.

A fresh clone has source code only. Create `.env` privately from the template or transfer your
existing `.env` through a private channel. Git does not transfer credentials, Docker volumes,
uploaded PDFs, saved console settings or notebook checkpoints.

For a fresh database with summaries/indexing enabled and direct OpenAI chat, configure these
before starting services and uploading. Add `OPENAI_API_KEY` to the private `.env`;
OpenRouter is only needed for work captured with that route:

```dotenv
FOLIO_DEVELOPMENT_MODE=true
FOLIO_SUMMARY_ENABLED=true
FOLIO_INDEX_ENABLED=true
FOLIO_CHAT_GATEWAY=openai
FOLIO_CHAT_REWRITE_GATEWAY=openai
FOLIO_MEMORY_GATEWAY=openai
```

The allowance is shared across the evaluation, not automatically shared between two separate
databases. For a fresh Mac database, set `FOLIO_SUMMARY_BUDGET_USD` to the agreed **remaining**
allowance before any paid work, and keep the existing per-document cap. Stop paid testing on the
old installation while using that remainder. If transferring the full database and artifacts
instead, preserve its usage ledger and original total; do not deduct spending twice.

On an existing database, the saved summary switch takes precedence over the environment seed.
Check the development console before uploading. Disabled jobs are not backfilled by changing
settings afterward. Model IDs/providers remain independent of the gateway switches above.

Start with a small PDF and inspect extraction, summary and index states before recording.
The Windows/Linux timings in the evaluation are not Mac measurements. If a timeout
occurs, inspect the saved error before changing parser/job/lease bounds together.
Do not claim that selecting the right architecture proves runtime compatibility.

For the notebook, install its optional kernel as described below and download its public PDF.
Use a new `RUN_DIR` for a fresh Mac database. Reusing Windows receipts without the corresponding
server records intentionally stops with a missing-resource error. The notebook does not copy
the old database or fabricate earlier results.

## Configuration

[`.env.example`](../.env.example) lists supported deployment values without usable credentials. Keep `.env`
private; concise comments and grouped settings are supported. Compose forwards selected values; settings for host processes also load `.env`. The
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

The env template selects direct OpenAI for every new AI stage. `OPENAI_API_KEY` supplies those
calls. `OPENROUTER_API_KEY` remains necessary for any older runs or indexes whose frozen policy
uses OpenRouter. Document, chat and memory workers receive both keys; neither reaches the API,
dispatcher or browser bundle. Missing/expired keys fail explicitly without provider fallback.

`FOLIO_SUMMARY_GATEWAY` and `FOLIO_INDEX_GATEWAY` select the document-stage routes. A new
upload captures these settings. Existing indexes keep their route for query embeddings, so
starting a new chat alone does not move an old index to OpenAI.

| Stage | Selected model and route | Default input/output tokens |
| --- | --- | --- |
| Summary | `openai/gpt-5.2`, provider `openai`, direct OpenAI | 64,000 / 4,096 |
| Document and question embeddings | `openai/text-embedding-3-small`, direct OpenAI; 1,536 dimensions | 512-token chunks; batches of up to 32 |
| Answer | `openai/gpt-5.2`, provider `openai` | 16,384 / 4,096 |
| Follow-up interpretation | `openai/gpt-5.2`, provider `openai` | 16,384 / 1,024 |
| Older-history notes | `openai/gpt-5.2`, provider `openai` | 16,384 / 2,048 |

Generation defaults to reasoning `none`. Summary settings are independent of chat.
Older OpenRouter summary profiles support Together's standard tier and Fireworks
without automatic fallback; new work defaults to direct OpenAI.
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

## Notebook walkthrough

Install the optional kernel with `uv sync --locked --group notebook`. Open
[`notebooks/folio_demo.ipynb`](../notebooks/folio_demo.ipynb) in a notebook-capable
editor and select this repository's `.venv` Python. No notebook server or global
kernel registration is required. Start the existing Docker stack first.

For VS Code, use its Python and Jupyter extensions. A working copy under ignored
`output/` keeps cell outputs out of the tracked notebook:

```sh
mkdir -p output/notebooks
cp -n notebooks/folio_demo.ipynb output/notebooks/folio_demo.ipynb
code . output/notebooks/folio_demo.ipynb
```

Choose **Select Kernel → Python Environments → `.venv`** (some versions first
show **Select Another Kernel**). Run code cells from top to bottom with their
play buttons. **Run by Line** steps through a cell; **Debug Cell** supports
breakpoints, including in the checkpoint helper. The Variables view shows the
current Python values. See VS Code's [notebook debugging guide](https://code.visualstudio.com/docs/datascience/jupyter-notebooks#_debug-a-jupyter-notebook).

Those debugger controls pause the notebook client. Docker workers continue after
an upload or question is accepted; use the inspection cells and worker logs to
observe their work. The notebook does not attach a debugger to those processes.

Download the public PDF linked in the notebook, then set `PDF_PATH` and a stable
`RUN_DIR` under `output/`. Run cells in order. Requests and responses are visible;
JSON snapshots persist beside the run manifest. Set `CAPTURE_WORKER_LOGS=True`
for bounded, filtered local Compose logs, retaining service and process labels.
Logs can have gaps; persisted attempts are the authoritative history.

Upload automatically schedules extraction, summary and indexing. Inspection
cells read their progress; they cannot pause workers between stages. A failed
summary does not block chat on a ready index. The question cells share one
conversation and show its source passages, usage and referenced history notes.
A short conversation may not trigger history compression.

After a timeout or kernel restart, rerun with the same directory. The
[`submit_once` helper](../notebooks/checkpoint.py) preserves request keys and
the original conversation head; it never refreshes an ambiguously accepted
request into a new question. Use a new intent name for a genuinely new question.
Keep one kernel per run, retain checkpoints, and stop if saved server IDs are
missing. Outputs may contain document content: clear notebook outputs before
committing, and keep executed copies under ignored `output/`.

The experimental [`retrieval` helper](../notebooks/retrieval.py) combines two
scoped candidate lists for evaluation. It is not selected by production chat.
The [evaluation](evaluation.md) distinguishes retrieved evidence, prepared
input cost and actual generated-answer support.

## Controlled retrieval comparison

[`scripts/evaluate_retrieval.py`](../scripts/evaluate_retrieval.py) contains the
whole experimental runner, including its self-checks. It compares original
vector-six/vector-twelve, same-page chunk grouping and a pinned local reranker
over all original chunks. A separate correct-source answer isolates generation.
It uses the existing worker's Torch/Transformers packages; it does not install
an application dependency or change the production selector.

Prepare a private labels JSON under `.local/retrieval-evaluation/`. It specifies
the index/revision IDs and questions with `id`, `question`, `split`, `answerable`,
`required_facts` and `oracle_chunk_ordinals`. Each fact supplies alternative
groups of `source_alternatives` IDs and all required `required_text` markers.
In the original comparison, the first question must include its original
`turn_id`; its prompt is verified against the saved hash. Inspect table relationships yourself: source/marker
coverage is a useful check, not proof that every generated claim is supported.

From the repository root, first run without `--execute` to check the plan.
The following command executes paid calls within the stated envelope:

```sh
docker compose run --rm --no-deps -T \
  -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 \
  -v "$PWD:/workspace" --entrypoint python worker \
  /workspace/scripts/evaluate_retrieval.py \
  --labels /workspace/.local/retrieval-evaluation/labels.json \
  --output /workspace/.local/retrieval-evaluation/baseline-new \
  --execute --max-usd 0.12
```

The temporary runner downloads pinned reranker weights into the ignored cache;
the normal document worker retains its offline settings. Run the same script
with `--self-test` for packing, coverage, replay and accounting checks. With a
database URL, accounting checks use a session-local shadow account and never
change the live allowance.

`ledger.json` records full paid inputs, responses, timing, usage and reservations;
`results.json` records retrieval ranks, coverage and generated answers. Both are
private. The script caches completed paid responses; re-execution measures local
scoring again, so preserve the initial results if comparing timing samples.
Changed code, source or labels require a new output directory. Unknown calls
are not repeated. An interrupted debit/refund stops for reconciliation against
the journal's recorded limits; do not delete its ledger to bypass that check.

Evaluation usage is recorded separately from application-turn metrics. The
runner temporarily reserves existing global/document headroom, then restores
unused allowance while carrying actual or uncertain evaluation charges forward.
It does not increase the agreed budget or create artificial conversations.
Charges carry forward globally. Linked follow-up experiments also include prior
evaluation charges in document admission; ordinary application per-document
totals do not yet include external experiment charges.

To compare Jev against an existing completed run, add `TYPESAFE_API_KEY` to the
ignored root `.env`. The runner reads it directly; it does not add the credential
to ordinary services. This mode reuses the prior corpus, labels and baseline
results, with no new embedding calls or local MiniLM execution:

```sh
docker compose run --rm --no-deps -T \
  -v "$PWD:/workspace" --entrypoint python worker \
  /workspace/scripts/evaluate_retrieval.py \
  --labels /workspace/.local/retrieval-evaluation/labels.json \
  --jev-from /workspace/.local/retrieval-evaluation/run-02 \
  --output /workspace/.local/retrieval-evaluation/jev-01 \
  --repeats 1 --execute --max-usd 0.08
```

Each request batches one independent Score judgment per original passage. Only
the query is shared; each judgment sees its own candidate text. Rank by the score,
not confidence. A synthetic probe checks the pinned API contract before private
evidence is sent. Partial/malformed responses fail explicitly and retain observed
billing. Transport uncertainty is never retried automatically.

Earlier comparisons' exact runner sources are preserved beside their ignored
artifacts as `run-02/runner-source.py` and `jev-01/runner-source.py`. The current
script intentionally cannot replay those older runs as its own run: its source hash differs. Use
`--jev-from` to reuse the frozen evidence through the explicit comparison path,
or a new output directory for a new baseline run. Existing results remain intact.

For a fresh ready index, `--factorial-from` reuses the reference run's generation
model and controls, captures the current answer prompt/schema versions, and
compares four arms: original vector-six, grouped
vector-six, Jev on all original chunks, and Jev on all grouped chunks. Its labels
need no saved turn. It uses the production first-turn prompt with empty history;
this is not a claim that it matches an existing live turn's prompt hash. The
manifest freezes those versions and source hashes for exact replay. To evaluate
an index-preparation fix, upload the same source as a new document and remap the
unchanged source expectations; ready indexes retain their original plans.

```sh
docker compose run --rm --no-deps -T \
  -v "$PWD:/workspace" --entrypoint python worker \
  /workspace/scripts/evaluate_retrieval.py \
  --labels /workspace/.local/retrieval-evaluation/multidoc/guide/labels.json \
  --factorial-from /workspace/.local/retrieval-evaluation/jev-01 \
  --output /workspace/.local/retrieval-evaluation/multidoc/guide/run-01 \
  --repeats 3 --execute --max-usd 0.18
```

Replace `guide` with `nasa` for the second frozen corpus. These local fixture
directories are generated evaluation artifacts, not files supplied by a clone.
The runner refuses a second experiment directory for a document that already
has an evaluation ledger: replay its existing directory instead. A deliberate
follow-up needs explicit prior-charge accounting; never remove ledgers to bypass
admission. Exact replay retains paid responses and their original call times;
local cosine and preparation timings are recomputed.

Each query embedding is measured once and shared by the two vector arms. Grouped
embeddings are prepared once per index. Three alternating Jev calls per arm
measure timing and variability; only the first response supplies answer evidence.
Every question gets four generated answers, including unanswerable controls.
Results record full-index source coverage, final prompt tokens, individual timing
samples and incomplete status. Report retrieval components separately from
generation: these exclude application queue, database and UI time. A conservative
input estimate rejects oversized Jev requests without dropping candidates; it is
not TypeSafe's exact tokenizer. Source expectations absent from the index stay in
the evaluation, rather than being replaced by easier questions.

## Backend checks

Integration tests truncate their selected database. Use only the isolated `folio_test` database:
[the fixture](../tests/conftest.py) requires that URL suffix and clears documents, saved controls and budget
state. Never point tests at application data.

```sh
uv sync --locked
docker compose -p folio-check -f compose.test.yaml up -d --build --wait
docker build --platform linux/amd64 --target verification -t folio-verification:local -f docker/worker.Dockerfile .
docker run --platform linux/amd64 --rm --network folio-check_default --cpus 4 --memory 6g --memory-swap 6g -e FOLIO_DATABASE_URL=postgresql://folio:folio@postgres:5432/folio_test -e FOLIO_REDIS_URL=redis://redis:6379/15 folio-verification:local python -m pytest -m "not supervision" -q
```

Build the parser base first. The test database build includes pgvector. Parser checks use committed synthetic
PDFs and bundled models; model boundaries use controlled responses. They make no paid calls and do not measure
real answer quality.

For the native worker, build verification with `--platform linux/arm64` and
`--build-arg DOCLING_IMAGE=folio-docling:2.148.0-arm64`, and tag it
`folio-verification:arm64`. Use that platform and image in the test run as well.
The isolated database/Redis services can retain their existing amd64 architecture.

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

The optional native-hang probe uses a unique queue and takes roughly a minute.
ARM64 users substitute `--platform linux/arm64` and `folio-verification:arm64`
in this command too:

```sh
docker run --platform linux/amd64 --rm --init --network folio-check_default --cpus 1 --memory 512m --memory-swap 512m -e FOLIO_RUN_SUPERVISION=1 -e FOLIO_SUPERVISION_REDIS_URL=redis://redis:6379/15 --entrypoint timeout folio-verification:local --signal=TERM --kill-after=5s 100s python tests/test_supervision.py
```

It checks workhorse/same-group descendant cleanup; detached process groups are outside that guarantee. The
one-second job timeout includes RQ's longer parent allowance. Ownership/retry checks remain separate. Model
quality needs a budgeted [evaluation](evaluation.md).

Dependency changes use `uv lock`, then `uv export --no-dev --no-emit-project -o requirements.lock` and
`uv export --no-emit-project -o requirements-dev.lock`; commit the lock/export files together. Add a new
numbered migration instead of editing an applied one. Parser changes require deliberate image, asset and
source-version updates.
