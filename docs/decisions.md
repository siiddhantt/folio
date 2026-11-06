# Folio decision guide

Updated: 2026-11-06. All recommendations below are proposals unless marked accepted.

Each discussion should cover: the user's outcome, two or three realistic options, what each costs, a recommendation, an example, and evidence that could change the recommendation. Resolve dependent questions in order rather than approving the whole stack at once.

## Accepted direction

- Name: Folio.
- General-purpose document assistance, using fact-checking in reports/documents as initial examples. These examples do not constrain content domains.
- Public source development; no public-service deployment implied.
- OpenRouter as the initial API gateway. GPT-6 Luna is a preferred evaluation candidate; the exact runtime model and its quality remain to be validated.
- PDFs with native text and English OCR, with one selected PDF per conversation. Docling is the selected parser; DOCX and other formats remain deferred.
- Preserve usable partial extraction with explicit coverage warnings; do not globally block summaries/chat when recoverable evidence exists.
- Develop locally with Docker from the start. Validate Docling and LiteParse on the same fixtures before deciding parser and expanded-format support.
- Small testable vertical slices, behavior tests first, explanations and human ownership throughout.
- A commentless local `.env` for secrets and adjustable runtime configuration, excluded from Git. A safe `.env.example` describes supported names through examples; explain their meaning in documentation.

## D01: First useful outcome

Accepted direction: understand documents and answer questions with checkable source evidence. The initial examples involve reports and ordinary documents.

A persona gives us realistic questions to evaluate; it does not restrict the product's schema or branding. We have not conducted customer interviews and must not present assumptions as research findings.

## D02: Supported documents and evidence

Status: PDF native text plus English OCR accepted after the local comparison. DOCX/other formats remain deferred. Usable partial extraction with coverage warnings is accepted; detailed table handling, additional languages, encryption, and numerical limits remain open.

| Option | Benefit | Cost |
| --- | --- | --- |
| Text-based PDF first | Stable page references, focused parser/quality checks | Scans and other formats are not supported initially. |
| PDF plus TXT/DOCX | Useful breadth for everyday documents | Different source locators; DOCX pagination is unstable without rendering. |
| PDF including scans | Covers a common real-world gap | OCR, model assets, more processing time, and more failure/quality cases. |

Decision: accept PDFs with native text and English OCR, using Docling; add other formats later. This limits formats rather than subject matter. The comparison verified clean English scans and mixed pages. Noisy/rotated/handwritten inputs need further quality examples. Decide detailed table behavior, encrypted inputs, and size/page/time limits before the first application slice.

Accepted extraction policy: retain the original, recoverable content, and known diagnostics; allow summaries and chat over that content with explicit coverage warnings. A question about a readable passage can still be answered with its citation. A summary must describe itself as covering the available content. If information is not found while coverage is incomplete, do not claim that it is absent from the original document. If no usable content exists, return a useful unavailable result. A page with no text is not automatically a scan; it may be blank. Detection cannot prove that every passage was extracted correctly.

Proposed reprocessing design: preserve processing revisions and source locators so later OCR can add missing content without silently rewriting old citation evidence. Exact state names, revision storage, atomic index replacement, and summary refresh behavior remain design choices.

Example: a PDF page says a report covers April-June. A correct answer should identify the period and show that passage. A photograph of the same page needs OCR before retrieval can see it.

## D03: Conversation scope and answer policy

Status: one selected PDF per conversation accepted. Answer and insufficient-evidence policies remain open.

- One selected document: simplest scope and evidence verification; multi-turn questions still work.
- A selected set: enables comparison but adds conflicts, cross-document citations, and more retrieval cases.
- Entire library: convenient discovery, but ambiguity and unintended source mixing become harder to control.

Decision: one document initially, with explicit document IDs in the retrieval boundary. Proposed answer policy: offer grounded answers, useful clarification, or an honest insufficient-evidence result, without adding outside factual claims. A larger collection of uploaded files must not broaden a conversation's scope.

Example: "What about next year?" needs the prior question to identify the subject; it still needs document evidence for next year's answer.

## D04: Runtime, storage, and access

Status: local development with Docker accepted. Hosting and access controls for any hosted service remain separate decisions.

Later runtime options: authenticated private service or public multi-user service. Public multi-user operation adds access control, quotas, retention, and abuse/spending concerns. Publishing source code does not select it.

Decision: reproducible local containerized services first. Docker Compose is the proposed local service runner. Compare local volumes with S3-compatible storage based on the runtime and worker's access. Define retention and deletion before claiming user data can be removed. Containers need bounded resources, durable volumes, health checks, and tested restart behavior; packaging alone is not a production-readiness claim.

## D05: Processing state and queue

Status: open. The [evidence and processing proposal](ingestion-design.md) compares a single document status with separate execution, availability, and coverage observations using a concrete report.

Choose observable behavior before a library: what is accepted, what is queued, when evidence becomes available, which failures can retry, and what happens after a worker or broker restart.

Options: RQ + Redis for a small job workflow; Celery + Redis for richer task/retry/routing controls. Neither removes the need for durable application state. In-process HTTP background work alone is not the proposed processing queue.

Recommendation: select the simpler queue that meets the recovery contract. Persist attempts/status. Make repeated execution safe: rerunning a job should not duplicate chunks or overwrite a newer document state.

Discuss the gap between committing a document and publishing its job: recoverable pending records with reconciliation versus a transactional outbox. Do not claim exactly-once delivery. Define summary failure independently from retrieval readiness if partial success is allowed.

## D06: Parser and source model

Status: Docling selected after the approved local comparison, with PDFs and English OCR; DOCX deferred. Detailed source contract remains open. See the [measured ingestion results](ingestion.md#results).

The [source-model proposal](ingestion-design.md#what-to-store) compares page text, raw Docling coupling, and a small immutable Folio evidence model plus original/raw artifacts. Its revision identities, element model and publication rules remain proposed until accepted.

| Option | Useful for | Limitations |
| --- | --- | --- |
| Docling | Structured layouts, tables, OCR, richer provenance and partial-result diagnostics | Local model assets and processing resources; verify output and source granularity. |
| LiteParse | Native spatial extraction, OCR, page diagnostics, layout/table blocks, optional Office conversion | Spatial reconstruction has limits; Office conversion and OCR need their dependencies and provenance checks. |
| Managed parsing | Outsourced parser execution and richer document models | Additional service, per-use costs, data transfer, and provider-specific failure contracts. |

Decision: use one Docling integration, informed by identical synthetic fixtures under matching Docker limits. Preserve document identity, physical PDF page, text span, parser version, and known diagnostics; inspect bounding boxes and table associations. Use existing OCR/layout machinery. A parser does not own Folio's conversation scope, durable processing history, or answer policy.

Result: both recovered the expected text/OCR facts; Docling preserved both tables' headers and cell relationships while LiteParse would require additional reconstruction. Docling used more time and memory for these PDFs. Both missed the damaged page as a structured error. Use the selected single engine without dual-parser routing. English OCR is accepted; DOCX source inspection is deferred. Six small synthetic fixtures are not general accuracy or production-performance evidence.

Do not equate empty text with definitive evidence of a scan. Report insufficient extraction and inspect page coverage. Do not flatten tables without checking whether row/column meaning survives.

## D07: Chunking

Status: open.

Chunking divides extracted text into pieces that retrieval can return and the model can read.

Options: fixed token windows with overlap; paragraph/section-aware token-bounded pieces; structured parser chunks when a richer parser is selected.

Recommendation: start with paragraph-aware pieces under a token limit, retaining all source spans. Compare a fixed-window baseline before claiming improvement. Choose size/overlap from evidence; avoid magic values presented as universal best practice.

Example: a condition at the end of page 2 may qualify a claim on page 3. Splitting them can lose meaning; joining them must retain both source locators. Large chunks add context but consume tokens and can dilute the relevant passage.

## D08: Retrieval strategy

Status: open.

| Option | Strength | Weakness |
| --- | --- | --- |
| Lexical search | Exact words, identifiers, and numbers | Can miss paraphrases. |
| Dense embeddings | Similar meanings despite different wording | Similarity does not guarantee factual relevance or exact identifiers. |
| Hybrid retrieval | Combines candidate lists from both | More moving parts and parameters to evaluate. |

Recommendation: establish lexical and dense baselines on the same human-reviewed questions, then choose the smallest approach that meets agreed needs. Postgres full-text search is available without a separate search service. Fusion/reranking should earn their cost through observed errors.

Measure whether expected evidence appears among the retrieved results. Do not use a universal cosine threshold as a truth detector. Decide candidate count, reranking, adjacent-span expansion, and evidence budget only after inspecting misses.

## D09: Retrieval storage

Status: open. PostgreSQL is fixed; pgvector is not.

| Option | Why choose it | What we take on |
| --- | --- | --- |
| PostgreSQL + pgvector | One data system for metadata, evidence, and vectors | Extension dependency and index/query tuning. |
| PostgreSQL + Qdrant | Dedicated vector/hybrid retrieval and independent scaling | Two data systems, synchronization, stale indexes, and coordinated deletion. |
| Postgres numeric arrays + exact scoring | Tiny baseline where extensions are unavailable | Custom dimension validation/scoring, data movement, and scaling work. |

Recommendation: pgvector with exact search for the initial small corpus, if supported by the chosen environment. This avoids a second service while leaving a measured migration path. It is a recommendation, not an accepted choice.

Exact versus approximate search is a separate decision. pgvector supports both. Exact nearest-neighbor recall means the mathematical nearest vectors were found, not that they contain the right answer. Add approximate indexes only after relevant latency/recall measurements.

Keep a narrow retrieval operation that accepts a question and permitted document scope and returns evidence plus provenance. Implement one backend first. Qdrant remains possible later, but migration still needs reindexing, consistency checks, and evaluation; an interface does not make it free.

## D10: Generation, summaries, and frameworks

Status: OpenRouter selected as the API gateway. GPT-6 Luna is a preferred evaluation candidate; model choice, prompts, and orchestration remain open. See [verified model notes](models.md).

Options: direct SDK calls with explicit orchestration; a small LlamaIndex integration; a small LangChain integration. Compare source mapping, testability, dependencies, and how much control flow remains visible. No current need for an autonomous-agent runtime.

Recommendation: keep retrieval, evidence formatting, generation, and validation understandable regardless of library. Preserve provider metadata behind a small boundary; do not implement unused providers.

Discuss generation and embeddings separately. A generation-model change needs quality evaluation. An embedding-model or dimension change changes the vector space and can require re-embedding all indexed content.

Model identity, input/evidence/history budgets, output reservation, and reasoning effort should be adjustable through validated configuration. A model's advertised capacity is a provider limit, not a recommended request size. Do not silently switch model aliases or provider routes during comparisons. See [configuration](configuration.md) for the proposed controls and their constraints.

Agree summary length/focus and insight fields. For long documents compare a bounded full-document prompt with chunk summaries followed by synthesis. Record truncation/coverage; a fluent summary must not imply it read unseen pages.

A response should distinguish answer, evidence references, and insufficient-evidence/clarification outcomes. Check that references belong to supplied evidence; separately evaluate whether the cited passages support the claims.

## D11: Quality, tests, and budgets

Status: method accepted; concrete fixtures and thresholds open.

Start with a small manually checked set: ordinary factual questions, an exact identifier, a table, a boundary-spanning answer, missing information, a follow-up, a misleading embedded instruction, and an unreadable/unsupported file.

Software tests: one observable behavior at a time; fail first, then implement and simplify. Include genuine persistence/retry/scope boundaries. Avoid exact prose assertions for model answers, tests of helper call order, and a second copy of the implementation as the expected result.

Live evaluations: inspect extraction, retrieval, answer support, citation correctness, abstention, and conversation behavior separately. Record versions and latency/usage. Establish a held-out set before tuning. A small sample finds errors but does not justify a general accuracy claim.

Agree a maximum live-evaluation spend, a per-document limit, and a response budget before running paid calls. Account credits are not the same as a product budget. Report unknown costs and unavailable usage fields rather than inventing them. Calibrate any later model judge against human labels.

## D12: API shape, performance, and monitoring

Status: open; follows the user/state contracts.

Decide resource routes and response models for documents, processing attempts, conversations, messages, insights, statistics, and processing metrics. Define pagination/order, not-ready responses, invalid input, provider timeout, and retry semantics. API errors should help the caller act.

Persist enough information to explain slow and failed work. Compare simple database-derived metrics with additional instrumentation only as needed. Choose health/readiness checks that reflect the dependencies actually used. Agree latency targets on specified hardware/data before optimizing.

Keep operational logs useful while avoiding raw private documents and secrets. Include correlation identifiers; decide retention and redaction.

## D13: Interface and optional growth

Status: open, after the core journey.

Options: documented API walkthrough; minimal upload/status/chat/source UI; richer dashboard. Recommendation: prove the API journey first, then consider a minimal interface if it improves source verification.

Select multi-document chat, streaming, caching, tagging, comparison, and other optional work from the requirements ledger individually. Evaluate cache invalidation, interrupted streams, versioning, and access scope before implementation.

## D14: Configuration and reproducibility

Status: commentless `.env` and configurable model/token budgets accepted; concrete values follow design and verification. OpenRouter credential and base URL names are documented. No application loader exists yet.

Keep secrets and adjustable deployment settings in the ignored local `.env`, with a commentless safe `.env.example`. Validate values at startup and document them in prose. Pin dependencies separately. Version prompt templates, schemas, and evaluation data in source rather than putting whole prompts into environment variables.

Potential settings include model IDs, service URLs, file limits, processing timeouts, chunking parameters, retrieval limits, log level, and usage budgets. Add each only when its behavior exists; do not fill the file with speculative flags. Values affecting embeddings/indexing require a compatible rebuild or explicit rejection.

## Proposed slice order after decisions

1. Upload one supported document, process it, and inspect its extracted content and source locations, including a useful failure result and stored processing measurements. No model call is needed for this slice.
2. Produce and inspect a persisted summary and agreed insights, including coverage and provider-failure behavior.
3. Ask one question and inspect its source evidence, including an unanswerable question and a scope-boundary check.
4. Continue and revisit a conversation, preserving context, citations, and failure semantics.
5. Recover interrupted/repeated work and expose complete document/processing metrics; finish reproducible setup and demonstration.
6. Add one selected optional user benefit, if it earns its scope.

Each slice contains its own contract tests, implementation, integration verification, review, and explanation. Slice 5 deepens failure recovery; earlier slices must not rely on knowingly broken status, retries, or persistence. This is a proposed sequence: settle each slice's behavior and dependencies before implementing it.

## Evidence for discussions

- [FastAPI background work](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat)
- [Celery tasks and retries](https://docs.celeryq.dev/en/stable/userguide/tasks.html), [RQ failures/retries](https://python-rq.org/docs/exceptions/), [Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [pypdf extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html), [pdfplumber](https://github.com/jsvine/pdfplumber), [Docling source model](https://docling-project.github.io/docling/concepts/docling_document/)
- [pgvector](https://github.com/pgvector/pgvector), [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/), [PostgreSQL text search](https://www.postgresql.org/docs/current/textsearch-intro.html)
- [LlamaIndex citation engine](https://developers.llamaindex.ai/python/framework-api-reference/query_engine/citation/)
- [RAG evaluation workflow](https://github.com/ai-evals-course/evals-skills/blob/main/skills/evaluate-rag/SKILL.md), [AI evaluation FAQ](https://hamel.dev/blog/posts/evals-faq/)
- [Test-first agent workflow](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/)

These sources explain capabilities and tradeoffs. They do not establish one universally agreed architecture or substitute for Folio-specific evidence.

Practitioner posts read directly on 2026-11-06 reinforce two useful habits:

- [Hamel Husain on task-specific evaluations](https://x.com/HamelHusain/status/2118383681031254059): measure the actual system and keep its evaluation cases maintained. This supports realistic document/question fixtures rather than borrowing a generic model leaderboard as a quality claim.
- [Boris Cherny on verification loops](https://x.com/bcherny/status/2007179861115511237): give a coding agent a concrete way to check its result. This supports executable acceptance checks and working demonstrations; it does not establish a universal productivity multiplier.

These are practitioner recommendations, not a formal standard or agreement on a particular vector database or framework.
