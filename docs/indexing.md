# From saved evidence to a ready index

Implemented November 12, 2026. Folio can turn a saved extraction into source-linked
chunks and persist their embeddings in PostgreSQL with pgvector. An embedding is
a list of numbers representing the chunk's meaning for later comparison with a
question. This increment prepares that searchable material; question retrieval
and answers are not implemented yet.

## Follow one document

The public FEMA Dwelling Form provides a concrete example: the garage clause on
physical PDF page 5 belongs with its limit and qualifications. Docling groups
related material, keeps heading context and merges compatible small pieces.
Every final piece is checked against the 512-token default, including its
headings. Its source links point back to existing evidence in the same revision.
They identify whole source elements, not verified character-level spans.

```text
saved extraction + frozen policy
  → verify artifact → prepare and save complete chunk plan
  → reserve allowance → embed one batch → save vectors
  → repeat missing batches → ready
```

1. **Capture intent.** A new upload saves its indexing configuration alongside
   ingestion and summary settings. Publishing usable extraction creates the
   index record in the same database transaction. Indexing and summarization
   can then proceed independently. Changing settings does not change accepted
   work. Disabled indexing creates an `unavailable` record with its reason.
2. **Deliver work.** The existing dispatcher places a reference to the index on
   the existing RQ/Redis queue. PostgreSQL keeps the durable intent. A worker
   claims it with an ownership token and expiry time; a duplicate delivery cannot
   claim an already-running index.
3. **Prepare once.** The worker verifies the saved Docling artifact's hash, runs
   HybridChunker with merging and heading preservation, validates source links
   and saves the complete plan atomically. This reuses extraction; it does not
   parse the PDF again. The manifest records versions, limits, exclusions and
   known extraction diagnostics.
4. **Call in batches.** Each delivery handles one batch of at most 32 chunks.
   Before calling OpenRouter, the worker checks the selected OpenAI route and
   reserves spending allowance. The network call runs outside the database
   transaction, so waiting on a provider does not hold database locks.
5. **Checkpoint results.** Validate the returned model, one response position per
   input, 1,536 finite values per vector and nonzero vectors. Save the vectors,
   billing observation and attempt outcome in a transaction under current
   ownership. A successful batch remains saved if a later batch fails.
6. **Publish completeness.** More missing vectors return the index to `pending`.
   Only a complete saved plan becomes `ready`. The chunk endpoint returns 409
   before readiness, preventing consumers from mistaking a partial index for a
   complete one.

For an existing revision without an index, `POST /revisions/{revision_id}/index`
creates one using configuration at that explicit request. Repeating the POST
returns the existing index, including its original policy and terminal outcome;
it does not regenerate chunks, restart failed work or spend again. There is no
automatic backfill of old revisions. `GET /revisions/{revision_id}/index` reads
status; `GET /revisions/{revision_id}/index/chunks` reads ready chunks with bounded
pagination and source links.

## What persists

| Record | Purpose |
| --- | --- |
| `document_indexes` | One index per extraction revision; frozen policy, manifest, expected chunk count, state, ownership and delivery information. |
| `index_chunks` | Exact submitted text, token count, hash, order, batch membership and nullable `vector(1536)`. |
| `chunk_sources` | Ordered body/context links to existing source elements; composite foreign keys prevent cross-revision links. |
| `indexing_attempts` | Each claimed delivery, its batch if reached, timestamps and saved safe failure details. |
| `embedding_invocations` | Each reserved provider call, input identity, observed usage/cost and uncertain billing. |

`pending` means eligible now or waiting for the next retry; `running` means one
worker currently owns the work. `ready` means every planned chunk has a vector.
`unavailable` explains a policy, budget or supported-configuration limit;
`failed` records a terminal processing or delivery failure. `not_started` is a
read response for a revision with no index row.

The ordinary database indexes serve specific queries: `indexes_due` finds
pending delivery work, `indexes_expired` finds lost owners, and `chunks_batch`
fetches a batch within one index. These are not approximate vector-search
indexes. No HNSW/IVFFlat index or similarity-search endpoint is added here.

## Failure and spending boundaries

| What goes wrong | What happens |
| --- | --- |
| Redis is unavailable or delivery disappears | The database intent survives. The dispatcher tries delivery again and records delivery errors; repeated terminated jobs hit the delivery-failure limit. |
| Worker stops or loses ownership | Expiry marks its attempt failed. Missing work can resume within the retry bound; a late worker cannot publish vectors. A late known bill can still settle its own reservation. |
| Provider timeout, rate limit or server failure | Retryable failures return to pending with bounded retries. Already-saved batches are reused. An uncertain call keeps its reservation. |
| Wrong model, missing/duplicate response positions or invalid vectors | Reject the batch and preserve any reported charge. No partial response is published. |
| Saved artifact or source mapping fails validation | Fail the index with an explicit reason. Original PDF, extraction and any existing summary remain usable. |
| Budget or configured chunk limit is reached | Index becomes unavailable; reading the document still works. No paid embedding call is started. |

Summaries and embeddings share the existing $1 cumulative and $0.40 document
allowances. The historical `summary_budget_account` row is their common lock:
one transaction checks totals and saves a reservation before another caller can
spend the same remaining allowance. Both features lock that row before their
own work record to keep lock ordering consistent.

Embedding admission reserves counted input tokens plus 16 tokens per chunk at
the configured price ceiling. A known actual bill replaces that reservation;
missing cost retains it. A timeout does not prove a call was free, and a retry
can incur a second charge. Ownership prevents duplicate publication, not
exactly-once provider billing. The budget is a pre-call admission boundary,
not a mechanism that cuts off an in-flight response.

Index settings are deployment configuration under `FOLIO_INDEX_*`, not new
console controls. Defaults are 512 tokens per chunk, 32 chunks per batch, at
most 4,096 chunks, a 60-second provider timeout and two attempts for consecutive
retryable failures; completing a batch resets that failure count. The model is
`openai/text-embedding-3-small`, explicitly routed to OpenAI through OpenRouter,
at 1,536 dimensions with no fallback. The shared budget retains the existing
`FOLIO_SUMMARY_*` budget names. Only the worker receives the API key.

## Inspect and explain the result

Activity shows the saved index state, embedded/expected chunk counts and latest
50 attempts, including batch, timing, input identity, cost or held allowance and
safe failure locations. It continues polling while indexing runs after
extraction finishes. It does not expose vectors, raw provider payloads or keys.

The November 12 live run finished **62 chunks in two successful embedding
calls**. Reported costs were $0.00017870 and $0.00014822: **$0.00032692 total**,
leaving **$0.767401976** of the shared allowance at that checkpoint. These are
observed execution results, not evidence of retrieval or answer accuracy.

Read the implementation in this order:

1. [Routes](../src/folio/indexing/routes.py) and
   [schema](../src/folio/migrations/008_document_indexes.sql): public outcomes and stored relationships.
2. [Chunking](../src/folio/indexing/chunking.py) and
   [preparation](../src/folio/indexing/preparation.py): exact text and source preservation.
3. [Processing](../src/folio/indexing/processing.py) and
   [lifecycle](../src/folio/indexing/lifecycle.py): one batch, ownership and publication.
4. [Provider boundary](../src/folio/indexing/provider.py),
   [shared budget](../src/folio/ai/budget.py) and
   [dispatcher](../src/folio/indexing/dispatcher.py): external calls, admission and recovery.

Owner exercise: inspect a saved chunk containing the garage clause and follow
its source links. Then read `next_batch` and `finish`: if the worker stops after
batch one commits, which rows survive, which batch is selected next, and why
can the chunk endpoint still refuse the incomplete index? The answer follows
from persisted vectors and the `ready` check, not Redis job history.

Current limits: one immutable index per revision; no reindex/replacement API,
query embedding, retrieval, answers or new conversation UI. Unsupported caption
or heading mappings fail explicitly instead of silently losing provenance.
Broader document-quality and throughput claims need separate evaluation. The
pinned PostgreSQL 18 + pgvector 0.8.7 image currently packages Linux **amd64**;
an ARM deployment requires an appropriate package/build rather than assuming
this image is portable to every host.
