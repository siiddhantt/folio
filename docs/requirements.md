# Folio requirements agreement

Status: ingestion accepted November 7; minimal interface and development inspection accepted November 9; automatic-only summary trigger accepted November 10; complete-input summaries, short-source output, revised spending limits and a development configuration console accepted by November 11; separate processing-run history, saved failure details and document indexing accepted November 12. First-answer retrieval and saved conversations are accepted; follow-ups remain the next increment. Updated: 2026-11-12.

This agreement separates product outcomes, engineering constraints, proposed behavior, and optional capabilities. A proposed detail is not accepted merely because it appears here.

## Purpose and first use

Folio is a general-purpose document assistant: upload documents, understand their contents, ask questions, and verify answers against the original evidence.

Accepted direction: use fact-checking in reports and ordinary documents as initial examples. This is a starting point for testing, not an industry restriction or a fixed document schema. Folio should not assume that every document is a contract, policy, or research paper.

Accepted initial boundaries: one selected PDF per conversation, with Docling processing native text and English OCR for scanned content. The local comparison informed this selection. DOCX, other formats, and multi-document conversations remain later options. Clean English scans were verified; noisy/rotated scans require further examples before quality claims.

Accepted extraction policy: preserve and use recoverable content when part of a document fails. Show known coverage limitations with document results, summaries, and answers. A summary of available content must not imply complete-document coverage. If no usable evidence remains, report that clearly; do not generate unsupported factual answers.

Accepted runtime and first slice: local Docker Compose with FastAPI, PostgreSQL, RQ/Redis and a shared artifact volume. The November 7 acceptance covers immutable source/evidence storage, request idempotency, durable work and ownership checks, bounded retries, initial input/resource limits and three test interfaces. See the [system contract](ingestion-system.md) and [verified status](status.md). Hosting remains separate.

Target core journey, delivered in stages:

1. A person uploads a supported document and immediately receives an identifier and processing status.
2. They can see processing progress, usable partial results, and known warnings or failures.
3. They read a summary and inspect stored document information.
4. They start a conversation about that document and ask a factual question.
5. They inspect the passage supporting the answer, ask a follow-up, and revisit the conversation later.
6. When a document or question cannot be handled, Folio explains the limitation clearly.

The first journey is verified through APIs. On November 9, a minimal upload/detail/source interface and development inspection view were accepted; see the [interface contract](interface.md). General-purpose means the content domain is flexible; it does not promise every file format, language, or document task.

## Core capabilities

| ID | Capability | Observable acceptance criterion to refine before implementation |
| --- | --- | --- |
| R01 | Intelligent upload and ingestion | First slice implemented: bounded PDF upload, immutable original and metadata, idempotent acceptance and useful invalid-input errors. Initial limits are 25 MiB and 100 physical pages; encrypted PDFs are terminal unsupported inputs. |
| R02 | Asynchronous document processing | Extraction, summaries and indexing run through RQ/Redis with durable PostgreSQL intent and bounded recovery. Indexing checkpoints one bounded embedding batch per job and publishes readiness only after every planned chunk has a vector. Request/attempt history remains inspectable. |
| R03 | Document retrieval | Metadata, processing state, original bytes and paginated revision evidence are available. A bounded Runs page lists accepted uploads and reopens documents separately from conversations. Filtering and content search remain open. |
| R04 | Summaries and AI insights | Automatically prepare a saved short overview and normally 3–5 cited key points (1–2 for short documents) from complete available evidence in one call per attempt, showing known gaps. No manual generation controls or generation on reads. Inputs over the selected limit remain readable with a summary-unavailable reason. Summaries and embeddings share the existing $1 cumulative and $0.40 document allowance, including retries/uncertain calls; indexing received no allowance increase. |
| R05 | Start a chat session | Save a conversation pinned to one ready PDF index. The first increment accepts one question; home lists saved conversations separately from Runs. |
| R06 | Ask a grounded question | Exact search retrieves at most six chunks from the pinned index. Return concise cited statements, clarification or insufficient evidence; preserve known gaps and validate citation membership. Semantic support is evaluated separately. |
| R07 | Chat history | Store and retrieve ordered user/assistant turns and their source context/citations. Specify persistence behavior when a model call fails. |
| R08 | Multi-turn context | Resolve a follow-up using relevant conversation context without changing the permitted document scope or treating a previous answer as independent evidence. |
| R09 | Document statistics API | Return real persisted document counts/status totals and agreed aggregate information. Do not substitute a static dashboard. |
| R10 | Processing metrics API | Request status exposes attempts, failures and measured parser duration. That duration includes admission, imports/setup, conversion and mapping, not queue wait or publication. Development inspection also exposes individual summary/indexing attempts, timing and known/uncertain billing. Aggregate metrics remain unfinished. |
| R11 | Durable data structures | Store document metadata/status, summaries/insights, conversations, messages/context/citations, processing history/metrics, and system performance observations. |
| R12 | Usable APIs and failure behavior | Provide coherent request/response models, useful errors, and API documentation. Unsupported operations and limits should be explicit. |
| R13 | Reproducible operation | Provide working backend source, setup/configuration instructions, and an architecture explanation alongside the implementation. |
| R14 | Demonstration | Provide a reproducible document-chat walkthrough and a video demonstrating actual working behavior. The video remains required and has not yet been produced. Use safe fixtures. |
| R15 | Transparent AI development | Maintain a concise AI-use record, design rationale, and versioned prompts with explanations of their goals and tradeoffs. |

## Engineering constraints and choices

| Item | Status |
| --- | --- |
| Python backend | FastAPI accepted November 7 and implemented. |
| PostgreSQL | Foundation constraint for persistent data. Start locally in Docker; hosting remains a later decision. |
| Task queue | RQ/Redis accepted November 7. PostgreSQL owns processing intent, attempts and the single retry policy. |
| File processing library | Docling selected after local comparison; PDF native text and English OCR. Structured evidence, diagnostics and initial bounds are accepted; wider quality checks remain open. |
| AI access | OpenRouter accepted as the initial API gateway. Summary models are compared against source support; compatibility and lifecycle limits are recorded in the model notes. Summaries and embeddings share the existing $1 total/$0.40 document allowance. The answer model remains open. |
| Embeddings | OpenRouter `openai/text-embedding-3-small` through the OpenAI route, at its default 1,536 dimensions, is accepted and implemented. Docling HybridChunker uses peer merging, heading preservation and a default 512-token ceiling. Exact submitted text, source links and policy are frozen per index. |
| File storage | Shared local Docker named volume accepted for opaque immutable originals/results. S3 is a future multi-host option, not an implemented backend. |
| RAG library | Summaries and indexing use direct provider calls and explicit orchestration; no RAG framework is introduced. LangChain or LlamaIndex remain options for a demonstrated later need. No requirement for an autonomous-agent runtime. |
| API documentation | FastAPI OpenAPI documents ingestion, summary and index status/chunk routes. Future capabilities need their own contracts. |
| Tests | Pytest behavior checks use real persistence/queue and offline parser fixtures. Accepted seams are HTTP-to-evidence, parser output and processing/recovery. |
| Retrieval store | pgvector 0.8.7 in the existing PostgreSQL 18 database is accepted and stores the vectors. Exact search is the selected starting direction; query embedding, ranking and search endpoints remain unimplemented. Approximate indexes and a second vector service remain deferred. |

The comparison and application pin Docling 2.148.0. Application dependencies are locked when introduced. Later model/library choices require explicit evaluation; the ingestion dependency selection does not settle retrieval or generation.

## Reliability and evidence contract

Accepted for ingestion: retain immutable originals, source identities/hashes, parser configuration, physical PDF pages, structured table meaning and attempt history. Publish usable evidence with known coverage warnings; zero usable content is unavailable. Detection cannot prove complete semantic recovery. Enforce accepted upload/page/time/resource bounds and retries. A PostgreSQL transaction publishes a complete revision; filesystem and Redis operations remain separate. Repeated delivery must not duplicate publication, and a stale worker must not overwrite newer work.

Accepted indexing binds a complete source-linked plan to one immutable extraction revision. Completed embedding batches survive bounded retries; partial vectors remain unavailable through the chunks endpoint until atomic publication. Known extraction gaps and declared exclusions remain visible. Every eligible body item must map to located evidence; unsupported source mapping fails indexing while the extraction and summary remain readable. Links identify whole source elements, not verified character spans. See the [indexing walkthrough](indexing.md).

Accepted conversation scope is one selected PDF. The first-answer increment pins a
ready index, saves one question and its terminal result, and preserves failed
questions. DeepSeek V4.1 Flash 1017/Together through OpenRouter starts with 16,384
input and 4,096 output tokens, reasoning off. Shared allowances are unchanged.
Accounting surrounds paid execution; retrieval and prompt preparation do not
make financial decisions. No subscriptions are included. Follow-ups, rewriting
and the accepted hybrid history compression are next; previous answers must
remain context rather than evidence. Uploaded text cannot change instructions
or permissions. See the [conversation contract](conversations.md).

## Optional capability ledger

Every item is accounted for. Deferred means intentionally outside the initial commitment; it is not rejected forever. Selection happens only after a cost/benefit discussion.

| ID | Capability | Initial disposition |
| --- | --- | --- |
| O01 | Multi-document chat | Deferred; compare selected sets with one-document scope in D03. |
| O02 | Suggested follow-up questions | Deferred; assess usefulness after basic follow-ups work. |
| O03 | Customizable summary length, focus, and tone | Deferred; choose one useful default first. |
| O04 | Automatic categorization and tagging | Deferred; avoid imposing a domain-specific taxonomy. |
| O05 | Sentiment analysis or deeper key-insight extraction | Deferred extension; define basic insights under R04 independently. |
| O06 | Comparative analysis across documents | Deferred; requires multi-document provenance and conflict handling. |
| O07 | Simple frontend/dashboard | Minimal upload/detail/evidence/source UI accepted November 9 with React, TypeScript and Vite. Light/dark appearance included; a separate Runs page accepted November 12. A richer dashboard remains deferred. |
| O08 | Real-time processing/chat updates | Deferred; polling is an initial option. SSE/WebSocket require a stated need. |
| O09 | Smart embedding/response caching | Deferred; define invalidation and scope keys before enabling. |
| O10 | Vector database integration | pgvector storage accepted and implemented in PostgreSQL 18. Exact search is the selected next direction; approximate vector indexes and other services remain deferred. |
| O11 | Streaming chat responses | Deferred; a final answer with verified source references is the first concern. |
| O12 | Broader test coverage | Grow with actual behaviors and failures. Core behavior verification begins in the first slice; no arbitrary coverage target. |
| O13 | AI cost tracking and optimization | Summaries and embeddings use one durable allowance with reservations and observed usage/cost; uncertain billed attempts retain their reservation. Broader optimization remains deferred. |
| O14 | Rate limiting and quotas | Decide with exposure and spending boundary. Required before an unrestricted public model-backed endpoint. |
| O15 | User-visible document version history | Deferred; internal immutable file/extraction provenance is implemented. Replacement/reprocessing APIs are not. |
| O16 | Batch processing optimizations | Deferred until measured workload justifies them. |
| O17 | Detailed logs/tracing/observability | Real stage events, correlated metadata logging and gated development inspection accepted November 9. A full tracing stack remains deferred. Aggregate metrics/history remain R09-R11. |
| O18 | Health and monitoring endpoints | Current health checks API/database availability. It does not certify parser accuracy, queue health or end-to-end readiness. Broader monitoring remains open. |

## Unknowns to resolve in order

1. Summary/insight usefulness and grounded-answer behavior for ambiguity, missing evidence and partial extraction, within the accepted one-PDF scope.
2. Follow-up resolution and the precise token triggers/schema for accepted hybrid history compression; first-answer retrieval and index binding are now selected.
3. Representative questions, wider OCR quality cases, latency expectations and an explicit live-evaluation budget.
4. Retention/deletion, backpressure, total storage limits and any later private/public hosting boundary.

Authentication, multi-tenancy, hosting, billing features, additional OCR languages and new workload limits are not silently assumed. Initial ingestion bounds are accepted starting policies, not measured capacity guarantees.

The November 11 development-console increment lets the owner save page/file-size
limits, a parser timeout within the worker's execution window, automatic-summary
enablement, token limits and reasoning effort. Changes apply to new uploads only;
each upload preserves ingestion and summary settings together. The November 12
indexing increment also captures its environment-managed policy. Model/provider,
worker limits and spending state are read-only. This is local development tooling,
not a public administration, model-management or billing feature. See D16 and
the [console contract](development-console.md).

## Quality evidence

Three concerns receive comparable attention: thoughtful AI integration and transparent agent use; useful product behavior and scope judgment; maintainable implementation and reliable operation.

Start with human-reviewed documents and questions. Observe extraction, evidence retrieval, answer support, citation correctness, follow-up behavior, and failures separately. A small development set is useful for finding errors but is not statistical proof of general accuracy.

Consider thousands of documents in design discussion through asynchronous work, scoped retrieval, bounded resource use, pagination, and measured bottlenecks. Do not claim throughput or production readiness before measurement.

## Agreement rule

Accept an option in the decision log before implementing dependent behavior. Change this agreement when scope changes, recording the reason and consequence. Keep working capability and proposed capability visibly distinct.
