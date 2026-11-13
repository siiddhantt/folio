# Folio requirements

Updated 2026-11-13. Accepted scope is a general-purpose document assistant:
upload a PDF, understand its contents, ask follow-ups and verify source evidence.
Reports, policies and household guides are examples, not domain restrictions.

## Core workflow

| ID | Requirement | Current acceptance and remaining work |
| --- | --- | --- |
| R01 | Intelligent upload and ingestion | Bounded PDF upload, metadata, immutable original, idempotent acceptance and actionable input errors. Default 25 MiB/100 physical pages; encrypted inputs are unsupported. |
| R02 | Asynchronous processing | Durable intent, queue delivery, attempts, bounded retry/recovery and ownership checks for extraction, summaries, indexing and chat. |
| R03 | Retrieve documents | Metadata, status, original bytes, paginated evidence and a separate Runs list are implemented. Search/filtering is deferred. |
| R04 | Summaries and insights | Automatic saved overview plus normally 3–5 cited points, allowing 1–2 for short sources. One call uses all prepared evidence; oversized input has an explicit unavailable reason. Citation quality needs further work. |
| R05 | Start a chat | One ready PDF index per saved conversation; document selector, title from first answer, rename and retained-record removal. |
| R06 | Grounded answers | Exact scoped vector search supplies up to six chunks. Return cited statements, clarification or insufficient evidence. IDs are validated; semantic support remains a separate evaluation. |
| R07 | Chat history | Persist ordered questions, answers/failures and citations. Reload, cursor pagination and request replay are supported. |
| R08 | Multi-turn context | Resolve follow-ups, retrieve fresh evidence and preserve the transcript. Background older-history notes plus a bounded before-answer fallback are implemented. One live compaction retained tested facts; attribution errors remain. |
| R09 | Document statistics API | Aggregate persisted counts/status totals remain to be implemented. |
| R10 | Processing metrics API | Individual attempts, durations, failures and usage are inspectable. Aggregate processing metrics remain to be implemented. |
| R11 | Durable data structures | Metadata, evidence, summaries, indexes, conversations, context, processing history and usage persist in PostgreSQL/artifact storage. |
| R12 | Usable APIs and errors | Validated inputs, coherent routes and OpenAPI exist. Several success responses still need typed schemas and useful examples. |
| R13 | Reproducible operation | Docker setup, configuration, development checks and architecture are documented. Production capacity is not established. |
| R14 | Demonstration | Real upload-to-chat walkthrough is measured in the evaluation. A recorded video remains unfinished. |
| R15 | Transparent AI development | Keep accepted rationale, versioned prompts, focused verification and a concise AI-use record. |

## Boundaries

- Docling handles native text and English OCR. Preserve usable partial extraction
  and known gaps; an empty document cannot supply evidence. No claim of complete
  extraction follows from a successful parser status.
- Use physical PDF page references. A citation must belong to the active index;
  a valid ID alone does not prove the passage supports its claim.
- Conversation history is context, not PDF evidence. Notes may lose detail and
  cannot establish exact quotations. Corrections and ambiguity need explicit handling.
- New uploads capture processing, summary and indexing settings. Accepted turns
  capture generation profiles and limits. Retries keep those snapshots.
- Spending admission and settlement surround paid calls; they are separate from
  retrieval and prompt preparation. The existing evaluation allowance covers
  summaries, embeddings, answers, rewriting and memory without a new allowance
  per feature. Unknown usage remains reserved; resets must carry prior spending.
- Use local Docker, PostgreSQL, RQ/Redis and immutable artifact storage. No
  public deployment, authentication, multi-tenancy or subscription system is implied.
- Implement small complete behaviors test-first. Deterministic software tests
  and live source-quality checks provide different evidence.

## Optional capabilities

| ID | Capability | Disposition |
| --- | --- | --- |
| O01 | Multi-document chat | Deferred |
| O02 | Suggested follow-ups | Deferred |
| O03 | Custom summary length/focus/tone | Deferred; one default format |
| O04 | Categorization/tagging | Deferred |
| O05 | Sentiment/deeper insights | Deferred beyond cited overview/key points |
| O06 | Cross-document comparison | Deferred |
| O07 | Frontend/dashboard | Minimal document/chat UI implemented; richer dashboard deferred |
| O08 | Real-time updates | Bounded polling implemented; SSE/WebSocket deferred |
| O09 | Smart embedding/response caching | Deferred |
| O10 | Vector integration | pgvector exact search implemented; approximate indexing deferred |
| O11 | Streaming responses | Deferred |
| O12 | Broader tests | Add meaningful behavior/failure coverage; no arbitrary coverage target |
| O13 | Cost tracking/optimization | Persistent shared accounting implemented; further optimization deferred |
| O14 | Rate limits/quotas | Deferred; required with any unrestricted hosted model endpoint |
| O15 | Document version history | Internal immutable provenance implemented; replacement/reprocessing UI/API deferred |
| O16 | Batch optimization | Bounded embedding batches implemented; workload-driven optimization deferred |
| O17 | Detailed observability | Structured logs, stored events/failures and development inspection implemented; full tracing stack deferred |
| O18 | Health/monitoring | API/database health exists; it does not certify queue or model quality |

See [decisions](decisions.md) for accepted tradeoffs and [status](status.md) for
the current handoff. Requirements change through explicit scope decisions;
recommendations and research do not become acceptance by appearing in a document.
