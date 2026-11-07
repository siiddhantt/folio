# Folio requirements agreement

Status: first ingestion slice accepted November 7; later capabilities retain open design choices. Updated: 2026-11-07.

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

The first journey can be verified through APIs. A visual interface is a separate capability decision. General-purpose means the content domain is flexible; it does not promise every file format, language, or document task.

## Core capabilities

| ID | Capability | Observable acceptance criterion to refine before implementation |
| --- | --- | --- |
| R01 | Intelligent upload and ingestion | First slice implemented: bounded PDF upload, immutable original and metadata, idempotent acceptance and useful invalid-input errors. Initial limits are 25 MiB and 100 physical pages; encrypted PDFs are terminal unsupported inputs. |
| R02 | Asynchronous document processing | Extraction runs through RQ/Redis with durable PostgreSQL intent and bounded recovery. Analysis and indexing will join the asynchronous workflow when implemented. Request/attempt history remains inspectable. |
| R03 | Document retrieval | First slice exposes metadata, processing state, original bytes and paginated revision evidence. Library listing/filtering and later search remain open. |
| R04 | Summaries and AI insights | Persist a useful summary and an agreed insights representation linked to the document. An output that failed must not appear successful. Insight types and long-document strategy remain open. |
| R05 | Start a chat session | Create a conversation bound to one selected PDF. Follow-up questions and evidence retrieval preserve that document scope. |
| R06 | Ask a grounded question | Retrieve evidence and produce a contextual answer with resolvable citations. Agree the behavior for absent, conflicting, or ambiguous evidence. |
| R07 | Chat history | Store and retrieve ordered user/assistant turns and their source context/citations. Specify persistence behavior when a model call fails. |
| R08 | Multi-turn context | Resolve a follow-up using relevant conversation context without changing the permitted document scope or treating a previous answer as independent evidence. |
| R09 | Document statistics API | Return real persisted document counts/status totals and agreed aggregate information. Do not substitute a static dashboard. |
| R10 | Processing metrics API | Request status exposes attempts, failures and measured parser duration. That duration includes admission, imports/setup, conversion and mapping, not queue wait or publication. Aggregate metrics and later stages remain unfinished. |
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
| AI access | OpenRouter accepted as the initial API gateway. GPT-6 Luna is the preferred evaluation candidate, not a validated final model choice. Generation and embedding model identifiers, budgets, and supported capabilities remain open. |
| Embeddings | OpenAI embeddings or a local sentence-transformer are options. Choose and version the embedding space; a model change can require re-embedding. |
| File storage | Shared local Docker named volume accepted for opaque immutable originals/results. S3 is a future multi-host option, not an implemented backend. |
| RAG library | LangChain or LlamaIndex is a recommended option. Direct SDK orchestration is also considered; explain why if selected. No requirement for an autonomous-agent runtime. |
| API documentation | FastAPI OpenAPI documents current ingestion routes. Future capabilities need their own contracts. |
| Tests | Pytest behavior checks use real persistence/queue and offline parser fixtures. Accepted seams are HTTP-to-evidence, parser output and processing/recovery. |
| Retrieval store | Open decision. pgvector, a separate vector service, or a deliberately small exact baseline are alternatives. A named vector database is not a foundation constraint. |

The comparison and application pin Docling 2.148.0. Application dependencies are locked when introduced. Later model/library choices require explicit evaluation; the ingestion dependency selection does not settle retrieval or generation.

## Reliability and evidence contract

Accepted for ingestion: retain immutable originals, source identities/hashes, parser configuration, physical PDF pages, structured table meaning and attempt history. Publish usable evidence with known coverage warnings; zero usable content is unavailable. Detection cannot prove complete semantic recovery. Enforce accepted upload/page/time/resource bounds and retries. A PostgreSQL transaction publishes a complete revision; filesystem and Redis operations remain separate. Repeated delivery must not duplicate publication, and a stale worker must not overwrite newer work.

Accepted conversation scope is one selected PDF. Proposed later answer rules still need refinement: treat previous answers as context rather than evidence, preserve document scope in retrieval, distinguish valid citation IDs from actual support, and explain absent/ambiguous evidence. Uploaded text cannot grant permissions or override application instructions. Summary, search and insight stages should report their own outcomes; their exact contracts and output budgets remain open.

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
| O07 | Simple frontend/dashboard | Optional; decide after the API journey is coherent. React/Next.js are candidates, not locked choices. |
| O08 | Real-time processing/chat updates | Deferred; polling is an initial option. SSE/WebSocket require a stated need. |
| O09 | Smart embedding/response caching | Deferred; define invalidation and scope keys before enabling. |
| O10 | Vector database integration | Proposed pgvector starting option; Qdrant and other services remain alternatives. |
| O11 | Streaming chat responses | Deferred; a final answer with verified source references is the first concern. |
| O12 | Broader test coverage | Grow with actual behaviors and failures. Core behavior verification begins in the first slice; no arbitrary coverage target. |
| O13 | AI cost tracking and optimization | Lightweight usage measurement proposed; elaborate optimization deferred. Record unknown costs honestly. |
| O14 | Rate limiting and quotas | Decide with exposure and spending boundary. Required before an unrestricted public model-backed endpoint. |
| O15 | User-visible document version history | Deferred; internal immutable file/extraction provenance is implemented. Replacement/reprocessing APIs are not. |
| O16 | Batch processing optimizations | Deferred until measured workload justifies them. |
| O17 | Detailed logs/tracing/observability | Attempt errors, diagnostics and delivery logging exist; elaborate tracing remains deferred. Aggregate metrics/history remain R09-R11. |
| O18 | Health and monitoring endpoints | Current health checks API/database availability. It does not certify parser accuracy, queue health or end-to-end readiness. Broader monitoring remains open. |

## Unknowns to resolve in order

1. Summary/insight usefulness and grounded-answer behavior for ambiguity, missing evidence and partial extraction, within the accepted one-PDF scope.
2. Chunking, retrieval strategy/store, generation/summary strategy and revision binding for those stages.
3. Representative questions, wider OCR quality cases, latency expectations and an explicit live-evaluation budget.
4. Retention/deletion, backpressure, total storage limits and any later private/public hosting boundary.

Authentication, multi-tenancy, hosting, billing features, additional OCR languages and new workload limits are not silently assumed. Initial ingestion bounds are accepted starting policies, not measured capacity guarantees.

## Quality evidence

Three concerns receive comparable attention: thoughtful AI integration and transparent agent use; useful product behavior and scope judgment; maintainable implementation and reliable operation.

Start with human-reviewed documents and questions. Observe extraction, evidence retrieval, answer support, citation correctness, follow-up behavior, and failures separately. A small development set is useful for finding errors but is not statistical proof of general accuracy.

Consider thousands of documents in design discussion through asynchronous work, scoped retrieval, bounded resource use, pagination, and measured bottlenecks. Do not claim throughput or production readiness before measurement.

## Agreement rule

Accept an option in the decision log before implementing dependent behavior. Change this agreement when scope changes, recording the reason and consequence. Keep working capability and proposed capability visibly distinct.
