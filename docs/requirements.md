# Folio requirements agreement

Status: draft for discussion. Updated: 2026-11-06.

This agreement separates product outcomes, engineering constraints, proposed behavior, and optional capabilities. A proposed detail is not accepted merely because it appears here.

## Purpose and first use

Folio is a general-purpose document assistant: upload documents, understand their contents, ask questions, and verify answers against the original evidence.

Accepted direction: use fact-checking in reports and ordinary documents as initial examples. This is a starting point for testing, not an industry restriction or a fixed document schema. Folio should not assume that every document is a contract, policy, or research paper.

Accepted initial boundaries: one selected PDF per conversation, with Docling processing native text and English OCR for scanned content. The local comparison informed this selection. DOCX, other formats, and multi-document conversations remain later options. Clean English scans were verified; noisy/rotated scans require further examples before quality claims.

Accepted extraction policy: preserve and use recoverable content when part of a document fails. Show known coverage limitations with document results, summaries, and answers. A summary of available content must not imply complete-document coverage. If no usable evidence remains, report that clearly; do not generate unsupported factual answers.

Accepted runtime: local development with Docker from the start, followed by a separate hosting decision.

Proposed first journey:

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
| R01 | Intelligent upload and ingestion | Accept a declared supported file, persist an identity and metadata, return promptly, and reject unsupported/invalid input with a useful error. File validation rules and limits remain open. |
| R02 | Asynchronous document processing | Parsing, analysis, and indexing happen through a task queue. Status and processing history remain inspectable after the HTTP request ends. Recovery guarantees are decided explicitly. |
| R03 | Document retrieval | Retrieve document metadata, processing state, and the permitted original/extracted content through documented APIs. List/filter/pagination semantics remain open. |
| R04 | Summaries and AI insights | Persist a useful summary and an agreed insights representation linked to the document. An output that failed must not appear successful. Insight types and long-document strategy remain open. |
| R05 | Start a chat session | Create a conversation bound to one selected PDF. Follow-up questions and evidence retrieval preserve that document scope. |
| R06 | Ask a grounded question | Retrieve evidence and produce a contextual answer with resolvable citations. Agree the behavior for absent, conflicting, or ambiguous evidence. |
| R07 | Chat history | Store and retrieve ordered user/assistant turns and their source context/citations. Specify persistence behavior when a model call fails. |
| R08 | Multi-turn context | Resolve a follow-up using relevant conversation context without changing the permitted document scope or treating a previous answer as independent evidence. |
| R09 | Document statistics API | Return real persisted document counts/status totals and agreed aggregate information. Do not substitute a static dashboard. |
| R10 | Processing metrics API | Expose agreed durations, failures, attempts, and processing history with clear units and definitions. Failed attempts are observable. |
| R11 | Durable data structures | Store document metadata/status, summaries/insights, conversations, messages/context/citations, processing history/metrics, and system performance observations. |
| R12 | Usable APIs and failure behavior | Provide coherent request/response models, useful errors, and API documentation. Unsupported operations and limits should be explicit. |
| R13 | Reproducible operation | Provide working backend source, setup/configuration instructions, and an architecture explanation alongside the implementation. |
| R14 | Demonstration | Provide a reproducible document-chat walkthrough and a video demonstrating actual working behavior. The video remains required and has not yet been produced. Use safe fixtures. |
| R15 | Transparent AI development | Maintain a concise AI-use record, design rationale, and versioned prompts with explanations of their goals and tradeoffs. |

## Engineering constraints and choices

| Item | Status |
| --- | --- |
| Python backend | Foundation constraint. Framework choice open; FastAPI recommended. |
| PostgreSQL | Foundation constraint for persistent data. Start locally in Docker; hosting remains a later decision. |
| Task queue | Foundation constraint. Celery with Redis, RQ, or a justified equivalent; choose after the recovery contract. |
| File processing library | Docling selected after local comparison; PDF native text and English OCR. Source contract, resource/input limits, and wider quality checks remain open. |
| AI access | OpenRouter accepted as the initial API gateway. GPT-6 Luna is the preferred evaluation candidate, not a validated final model choice. Generation and embedding model identifiers, budgets, and supported capabilities remain open. |
| Embeddings | OpenAI embeddings or a local sentence-transformer are options. Choose and version the embedding space; a model change can require re-embedding. |
| File storage | Local filesystem or S3-compatible storage are options. Deployment and access boundaries drive the selection. |
| RAG library | LangChain or LlamaIndex is a recommended option. Direct SDK orchestration is also considered; explain why if selected. No requirement for an autonomous-agent runtime. |
| API documentation | Required product documentation; generated OpenAPI/Swagger or another usable form. |
| Tests | Pytest is the preferred Python candidate. Meaningful behavior checks precede application code. |
| Retrieval store | Open decision. pgvector, a separate vector service, or a deliberately small exact baseline are alternatives. A named vector database is not a foundation constraint. |

The comparison pins Docling 2.148.0. Application dependency versions otherwise remain open; use supported versions and lock them when introduced. Do not use historic model/library names as an unexamined implementation choice.

## Proposed reliability and evidence contract

These are recommendations awaiting acceptance alongside the relevant design decision.

- Preserve document identity, content version/hash, source locators, parser version, and processing attempt information.
- Preserve physical PDF page references; for unpaginated formats, use honest section/paragraph locators rather than invented page numbers.
- Accepted: retain usable partial extraction with explicit known-coverage warnings. Distinguish no usable content from a partially usable document. Detection cannot prove complete semantic recovery; never silently imply complete coverage.
- Bound retries, timeouts, input sizes, and generated output. Repeated work must not duplicate final document data.
- Keep selected document scope in every evidence query. Uploaded text cannot broaden scope, grant permissions, or override application instructions.
- Treat previous answers as conversation context, not source evidence. Questions requiring missing evidence should produce a useful limitation or clarification.
- Distinguish citation existence, correct source location, and actual support for a claim. All three matter.
- Distinguish ready-to-search status from separate summary/insight completion if those operations can succeed independently. Summaries and insights remain core capabilities.
- Define database/queue publication and crash recovery behavior. Do not promise exactly-once execution merely because a queue is present.

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
| O15 | User-visible document version history | Deferred; internal content/version provenance still needed for reliable citations. |
| O16 | Batch processing optimizations | Deferred until measured workload justifies them. |
| O17 | Detailed logs/tracing/observability | Minimal diagnostic events proposed; elaborate tooling deferred. Core metrics/history remain R09-R11. |
| O18 | Health and monitoring endpoints | Lightweight health/readiness proposed; choose checks that reflect actual dependencies. |

## Unknowns to resolve in order

1. Refine the accepted Docling/PDF/English-OCR boundary: source structure, table handling, encryption, file/page/time limits, and representative OCR quality cases. DOCX remains deferred.
2. Scope and user experience: one document or a set, source inspection, ambiguity, missing/partial evidence.
3. Local Docker details: retention/deletion, storage, available resources, and a later private/public hosting boundary.
4. Processing and recovery contract: stage states, safe retries, queue publication failures, and partial success.
5. Parser, provenance, chunking, retrieval strategy/store, and generation/summary strategy.
6. Representative fixtures, quality criteria, response/processing latency expectations, and an explicit live-evaluation budget.

Authentication, multi-tenancy, hosting, billing features, additional OCR languages/capabilities, and exact numerical limits are not silently assumed. They must be chosen or explicitly deferred.

## Quality evidence

Three concerns receive comparable attention: thoughtful AI integration and transparent agent use; useful product behavior and scope judgment; maintainable implementation and reliable operation.

Start with human-reviewed documents and questions. Observe extraction, evidence retrieval, answer support, citation correctness, follow-up behavior, and failures separately. A small development set is useful for finding errors but is not statistical proof of general accuracy.

Consider thousands of documents in design discussion through asynchronous work, scoped retrieval, bounded resource use, pagination, and measured bottlenecks. Do not claim throughput or production readiness before measurement.

## Agreement rule

Accept an option in the decision log before implementing dependent behavior. Change this agreement when scope changes, recording the reason and consequence. Keep working capability and proposed capability visibly distinct.
