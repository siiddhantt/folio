# Folio decision guide

Updated: 2026-11-09. All recommendations below are proposals unless marked accepted.

Each discussion should cover: the user's outcome, two or three realistic options, what each costs, a recommendation, an example, and evidence that could change the recommendation. Resolve dependent questions in order rather than approving the whole stack at once.

## Accepted direction

- Name: Folio.
- General-purpose document assistance, using fact-checking in reports/documents as initial examples. These examples do not constrain content domains.
- Public source development; no public-service deployment implied.
- OpenRouter as the initial API gateway. The first bounded summary evaluation uses GPT-5 Nano temporarily; its retirement and compatibility limits are recorded in the model notes. Chat and embedding models remain open.
- PDFs with native text and English OCR, with one selected PDF per conversation. Docling is the selected parser; DOCX and other formats remain deferred.
- Preserve usable partial extraction with explicit coverage warnings; do not globally block summaries/chat when recoverable evidence exists.
- Develop locally with Docker Compose. The completed Docling/LiteParse comparison informed parser selection.
- Accepted November 7: the complete first ingestion slice uses FastAPI, PostgreSQL, RQ/Redis and a shared local artifact volume, with the schema, idempotency, retry/ownership rules, bounds and test interfaces in the [system design](ingestion-system.md). Retrieval and generation remain separate decisions.
- Small testable vertical slices, behavior tests first, explanations and human ownership throughout.
- A commentless local `.env` for secrets and adjustable runtime configuration, excluded from Git. A safe `.env.example` describes supported names through examples; explain their meaning in documentation.

## D01: First useful outcome

Accepted direction: understand documents and answer questions with checkable source evidence. The initial examples involve reports and ordinary documents.

A persona gives us realistic questions to evaluate; it does not restrict the product's schema or branding. We have not conducted customer interviews and must not present assumptions as research findings.

## D02: Supported documents and evidence

Status: PDF native text plus English OCR accepted after the local comparison. On November 7, the owner accepted structured table evidence, physical-page provenance, terminal rejection of encrypted PDFs and the initial input/execution bounds. DOCX/other formats and additional OCR languages remain deferred.

| Option | Benefit | Cost |
| --- | --- | --- |
| Text-based PDF first | Stable page references, focused parser/quality checks | Scans and other formats are not supported initially. |
| PDF plus TXT/DOCX | Useful breadth for everyday documents | Different source locators; DOCX pagination is unstable without rendering. |
| PDF including scans | Covers a common real-world gap | OCR, model assets, more processing time, and more failure/quality cases. |

Decision: accept PDFs with native text and English OCR, using Docling; add other formats later. This limits formats rather than subject matter. Preserve table cells, headers, spans and supplied page locations. Initial bounds are 25 MiB and 100 pages, with parser/job/lease limits defined in the [system design](ingestion-system.md#accepted-initial-operating-bounds). The comparison verified clean English scans and mixed pages; noisy/rotated/handwritten inputs still need quality examples.

Accepted extraction policy: retain the original, recoverable content, and known diagnostics; allow summaries and chat over that content with explicit coverage warnings. A question about a readable passage can still be answered with its citation. A summary must describe itself as covering the available content. If information is not found while coverage is incomplete, do not claim that it is absent from the original document. If no usable content exists, return a useful unavailable result. A page with no text is not automatically a scan; it may be blank. Detection cannot prove that every passage was extracted correctly.

Accepted internal provenance: immutable file versions, extraction revisions and source locators preserve old evidence. Reprocessing/replacement APIs, atomic index replacement, conversation revision binding and summary refresh remain future decisions; the schema alone does not implement those features.

Example: a PDF page says a report covers April-June. A correct answer should identify the period and show that passage. A photograph of the same page needs OCR before retrieval can see it.

## D03: Conversation scope and answer policy

Status: one selected PDF per conversation accepted. Answer and insufficient-evidence policies remain open.

- One selected document: simplest scope and evidence verification; multi-turn questions still work.
- A selected set: enables comparison but adds conflicts, cross-document citations, and more retrieval cases.
- Entire library: convenient discovery, but ambiguity and unintended source mixing become harder to control.

Decision: one document initially, with explicit document IDs in the retrieval boundary. Proposed answer policy: offer grounded answers, useful clarification, or an honest insufficient-evidence result, without adding outside factual claims. A larger collection of uploaded files must not broaden a conversation's scope.

Example: "What about next year?" needs the prior question to identify the subject; it still needs document evidence for next year's answer.

## D04: Runtime, storage, and access

Status: local Docker Compose and a shared artifact named volume accepted November 7. Hosting and access controls for any hosted service remain separate decisions.

Later runtime options: authenticated private service or public multi-user service. Public multi-user operation adds access control, quotas, retention, and abuse/spending concerns. Publishing source code does not select it.

Decision: reproducible local containerized services first, with separate PostgreSQL, Redis and artifact volumes. Local API and workers share opaque immutable artifact keys. Multi-host workers would need shared storage such as S3 and a tested migration. Retention/deletion and online cleanup remain unimplemented. Packaging alone is not a production-readiness claim.

## D05: Processing state and queue

Status: accepted November 7. RQ/Redis transports work; PostgreSQL owns durable intent, attempts and the single bounded retry policy. Execution outcome, evidence availability and coverage observations are distinct.

The dispatcher recovers committed due work; an isolated Linux worker claims an authorized attempt before loading Docling. Publication and failure updates check the attempt, ownership token and lease. HTTP receipt uniqueness protects replay; a unique request-to-revision constraint protects publication. No exactly-once execution claim follows.

RQ was selected for the initial small workflow. Celery offers richer routing/pools; a PostgreSQL-native queue can combine enqueue with application transactions but needs its own native-parser isolation plan. See the [accepted system design](ingestion-system.md) for tradeoffs, bounds and failure behavior, and [status](status.md) for checks actually completed. Summary and retrieval stage states will be decided with those features.

## D06: Parser and source model

Status: Docling selected after the approved local comparison, with PDFs and English OCR; DOCX deferred. The small Folio evidence model, original/raw artifacts and diagnostic envelope were accepted November 7. See the [measured ingestion results](ingestion.md#results).

The [source-model rationale](ingestion-design.md#what-to-store) compares page text, raw Docling coupling, and the selected immutable Folio evidence model plus original/raw artifacts. Source mapping stays within the parser boundary.

The [implemented schema](ingestion-system.md#relational-schema) separates logical documents, immutable file versions, extraction revisions, requests/attempts and source locations. Relationships are normalized; table payloads, configuration and diagnostics use JSONB. Individual table cells are not relational rows.

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

November 9 source review: the running pinned Docling 2.148.0 environment contains
docling-core 2.106.0. Its HybridChunker supports repeated table headers and
token-bounded splitting/merging. This is a candidate to test before writing a
custom chunker, not a selected or evaluated chunking policy. Splits can retain
metadata for an entire source item, so precise subspan provenance must not be
inferred from the presence of chunk metadata. Mapping raw item references to
Folio's stored `provider_ref` and located source elements needs explicit checks;
unmapped or unlocated evidence must be reported. See the
[upstream chunking contract](https://docling-project.github.io/docling/concepts/chunking/).

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

Status: OpenRouter selected as the API gateway. Automatic-only, complete-input summary generation accepted November 10. The owner delegated cost-conscious model selection. After Nano and Mini source reviews exposed citation and qualification failures, GPT-5.1 on the verified OpenAI standard route became the current candidate. It is temporary, retires April 1, 2027, and does not establish general summary accuracy. See [verified model notes](models.md) and [recorded evaluations](summary-evaluation.md).

Options: direct SDK calls with explicit orchestration; a small LlamaIndex integration; a small LangChain integration. Compare source mapping, testability, dependencies, and how much control flow remains visible. No current need for an autonomous-agent runtime.

Recommendation: keep retrieval, evidence formatting, generation, and validation understandable regardless of library. Preserve provider metadata behind a small boundary; do not implement unused providers.

Discuss generation and embeddings separately. A generation-model change needs quality evaluation. An embedding-model or dimension change changes the vector space and can require re-embedding all indexed content.

Model identity, input/evidence/history budgets, output reservation, and reasoning effort should be adjustable through validated configuration. A model's advertised capacity is a provider limit, not a recommended request size. Do not silently switch model aliases or provider routes during comparisons. See [configuration](configuration.md) for the proposed controls and their constraints.

The summary format and complete-input path below are selected. Section summaries followed by synthesis remain a later alternative. Record coverage; a fluent summary must not imply it read unseen pages.

Accepted next increment: automatically create one saved, cited summary from all
usable evidence in one immutable extraction revision, using one model call per
attempt. If the complete input exceeds its limit, expose the summary's unavailable
reason and keep evidence usable; do not truncate or substitute search hits.
Section-note synthesis, embeddings and retrieval remain deferred.

The [summary contract](summaries.md) clarifies that source preparation comes
before generation. The bounded complete-input call is selected; section notes
and synthesis remain deferred. Embeddings are not required. It records input coverage,
durable reuse, uncertain provider outcomes and an illustrative token-cost
comparison. The owner selected automatic-only generation: no manual generation,
regeneration or resume controls, and no new generation merely from opening a
document. Automatic retries remain bounded within the same workflow. A shared
token-budget function checks instructions, evidence labels, structured tables,
output-schema overhead and a margin against the selected model/route limits.
Summary configuration is separate from future chat and embedding settings.

Accepted output on November 10: a short overview and 3–5 cited key points, with
known extraction gaps displayed. On November 11 the owner accepted 1–2 points for
short documents rather than filler. Points adapt to the source; separate fixed
findings/dates/risks sections are not required. After large-document research and
cost examples, the owner selected the complete-input-only path for this increment.
The 150-page design example does not increase the accepted ingestion page limit.

Implementation follows the existing durable PostgreSQL/RQ pattern, with a concrete
summary feature rather than a generic workflow framework. Publication creates its
intent atomically with evidence. Result and billing state are separate: a stale
worker cannot publish, and an uncertain billed call retains its reservation.

A response should distinguish answer, evidence references, and insufficient-evidence/clarification outcomes. Check that references belong to supplied evidence; separately evaluate whether the cited passages support the claims.

## D11: Quality, tests, and budgets

Status: behavior-first method and the three first-ingestion test interfaces accepted November 7. Summary checks extend HTTP/persistence and workers with deterministic model substitutes; live quality is separate. The owner initially accepted $1 cumulative and $0.10 per document, including retries and uncertain calls. On November 11 the document cap was raised to $0.40 for a stronger-model comparison after source review found failures; the $1 total is unchanged. Restarting services does not reset consumption. Completed checks are recorded in [status](status.md).

Start with a small manually checked set: ordinary factual questions, an exact identifier, a table, a boundary-spanning answer, missing information, a follow-up, a misleading embedded instruction, and an unreadable/unsupported file.

Software tests: one observable behavior at a time; fail first, then implement and simplify. Include genuine persistence/retry/scope boundaries. Avoid exact prose assertions for model answers, tests of helper call order, and a second copy of the implementation as the expected result.

Live evaluations: inspect extraction, retrieval, answer support, citation correctness, abstention, and conversation behavior separately. Record versions and latency/usage. Establish a held-out set before tuning. A small sample finds errors but does not justify a general accuracy claim.

Agree a maximum live-evaluation spend, a per-document limit, and a response budget before running paid calls. Account credits are not the same as a product budget. Report unknown costs and unavailable usage fields rather than inventing them. Calibrate any later model judge against human labels.

## D12: API shape, performance, and monitoring

Status: the first-ingestion API and stored attempt measurements were accepted November 7 and implemented. The summary slice adds a read-only revision summary resource and usage metadata. Chat resources, global statistics and broader performance targets remain open.

Current routes cover upload, document metadata/original, request/attempt status and paginated revision evidence. Status uses one consistent database snapshot; unique reading order supports evidence pagination. Remaining conversation, insight and aggregate APIs need their own acceptance criteria. API errors should help the caller act.

Persist enough information to explain slow and failed work. Compare simple database-derived metrics with additional instrumentation only as needed. Choose health/readiness checks that reflect the dependencies actually used. Agree latency targets on specified hardware/data before optimizing.

Keep operational logs useful while avoiding raw private documents and secrets. Include correlation identifiers; decide retention and redaction.

## D13: Interface and optional growth

Status: minimal ingestion interface accepted November 9, following the verified API journey. React + TypeScript + Vite was explicitly selected. Light/dark appearance and a development-only view of real processing details are included. See the [interface contract](interface.md).

The owner subsequently rejected the initial green editorial styling and selected
customized shadcn elements, a neutral palette and minimal visible copy. Use one
sans-serif family and compact document controls. Typography and spacing should
organize real content; avoid hero layouts, slogans and repeated explanations.

Options considered: API-only walkthrough; minimal upload/status/evidence/source interface; richer dashboard. The owner selected the minimal interface to inspect real uploads and understand backend execution before model-backed features. A small React/Vite client supports later source/chat interaction while the Python API remains authoritative; server-rendered templates would reduce frontend tooling but need more manual interaction handling.

Use actual persisted state and bounded polling. A server setting gates development inspection, and observed stage events carry real timestamps. Do not add canned scenarios, seeded runtime content, artificial progress or future chat/summary controls. Detailed tracing collectors, document listing and broader UI remain deferred. The browser journey and existing HTTP/persistence contracts are the agreed test interfaces for this increment.

Select multi-document chat, streaming, caching, tagging, comparison, and other optional work from the requirements ledger individually. Evaluate cache invalidation, interrupted streams, versioning, and access scope before implementation.

## D14: Configuration and reproducibility

Status: commentless `.env` and separate summary model/token budgets accepted. The ingestion and summary loaders validate their own settings. See [configuration](configuration.md) for implemented defaults, provider compatibility limits and the persistent spending allowance. Only the worker receives model credentials.

Keep secrets and adjustable deployment settings in the ignored local `.env`, with a commentless safe `.env.example`. Validate values at startup and document them in prose. Pin dependencies separately. Version prompt templates, schemas, and evaluation data in source rather than putting whole prompts into environment variables.

Potential settings include model IDs, service URLs, file limits, processing timeouts, chunking parameters, retrieval limits, log level, and usage budgets. Add each only when its behavior exists; do not fill the file with speculative flags. Values affecting embeddings/indexing require a compatible rebuild or explicit rejection.

## D15: Backend organization and debugging

The owner requested a grouped, minimal backend and effective debugging on
November 10. The selected implementation pattern is one `ingestion/` feature
package: routes, acceptance, processing, recovery, evidence reads and parsing
stay together. App assembly, configuration, database connections, artifact
storage, process logging and schema migrations remain shared at the root.

Alternatives considered: retain the flat layout; split documents from ingestion;
or introduce controller/service/repository layers. One feature package makes the
current complete workflow easier to follow without adding cross-feature ownership
or forwarding layers. Keep a narrow stable `folio.processing.process_attempt`
entry for RQ messages already stored with that import path. Other imports move
directly to their owning feature. A second implemented feature with real shared
behavior is the reason to revisit these boundaries.

Keep the existing PostgreSQL event timeline and standard Python logging. Use
structured process records with time, severity, component, request/attempt identity
and safe failure locations. Durable state remains authoritative: console output
is not a second job ledger. Exclude arbitrary exception messages and document
contents. A tracing collector and additional logging dependencies are deferred.

## Slice order and remaining decisions

1. Accepted, implemented and checked: upload one supported document, process it, and inspect persisted evidence, sources, warnings and attempt history. Idempotency, retry and interruption behavior belong in this slice; [status](status.md) records operational probe limits. The owner walkthrough remains part of the checkpoint. No model call is needed.
2. Produce and inspect a persisted summary and agreed insights, including coverage and provider-failure behavior.
3. Ask one question and inspect its source evidence, including an unanswerable question and a scope-boundary check.
4. Continue and revisit a conversation, preserving context, citations, and failure semantics.
5. Extend recovery across the later model-backed stages and expose aggregate document/processing metrics; finish the complete demonstration.
6. Add one selected optional user benefit, if it earns its scope.

Each slice contains its own contract tests, implementation, integration verification, review, and explanation. The remaining order is proposed: settle each slice's behavior and dependencies before implementing it. Do not defer basic persistence or recovery correctness to slice 5.

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
