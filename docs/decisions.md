# Folio decisions

Updated 2026-11-14. The choices below are accepted unless explicitly deferred.
Current implementation and remaining defects are in [status](status.md).
The earlier comparisons and detailed rationale remain in
[Git history](https://github.com/siiddhantt/folio/tree/1c793a9891e4aaf833acce53987eb7ee1beee3e0/docs).

## D01–D03: Product, files and conversation scope

Folio helps people understand documents and check answers against evidence.
Examples guide testing without imposing an industry-specific schema.
Accept PDFs with native text and English OCR; defer DOCX and other languages.
One conversation stays pinned to one ready immutable document index. A selected
collection or whole-library search would add scope ambiguity and conflicting
evidence, so multi-document chat is deferred.

Retain usable partial extraction with known coverage warnings. Stopping all work
because one page fails would discard useful content. No recovered content means
no evidence; successful extraction does not prove that every passage survived.
Preserve structured tables, physical pages and source identities. A blank page
and an unreadable page may both have no recovered text; do not invent the cause.

## D04–D06: Runtime, work and parsing

FastAPI, PostgreSQL, RQ/Redis and a shared Docker artifact volume were accepted
November 7. PostgreSQL owns work intent and state; Redis delivers jobs. Durable
dispatch, bounded retries and ownership checks handle repeated delivery and
interrupted workers. External calls and parsing happen outside database locks.
Originals and extraction revisions are immutable. An internal revision does not
implement user-facing replacement/reprocessing.

Docling 2.148.0 was selected over LiteParse after a local synthetic comparison.
It preserved stronger table relationships with higher measured time/memory in
that setup. Both missed the damaged-page signal; this was not a broad benchmark.
Default bounds are 25 MiB/100 pages and bounded parser/worker execution.
The worker checks pages before building the converter. Upload acceptance does
not mean parsing has passed. Raising one limit does not raise all other limits.

Local artifacts keep the first deployment understandable. Multi-host workers
would need shared object storage and its consistency/cleanup policy. Hosting,
authentication, backups and tenancy remain separate decisions.

## D07–D09: Chunking, embeddings and retrieval

Use Docling HybridChunker with peer merging, explicit heading preservation and a
512-token target. Map its references back to located stored evidence. Chunk
source links identify whole elements, not verified character-level highlights.
Unmapped eligible evidence fails indexing instead of disappearing silently.

Use OpenRouter `openai/text-embedding-3-small`, OpenAI route, 1,536 dimensions,
and batches of at most 32 chunks. Freeze submitted text, source links and policy;
reuse completed batches across bounded recovery. Publish the index only when all
planned vectors are stored. One index per revision is implemented; replacement
generations and automatic re-embedding are deferred.

Store vectors in pgvector 0.8.7 with PostgreSQL 18. Exact cosine search returns
up to six chunks inside the conversation's pinned index. This avoids a second
data service and establishes a small inspectable baseline. Exact nearest vectors
are not necessarily relevant evidence. Qdrant, lexical/hybrid retrieval,
reranking and approximate indexes remain options requiring measured benefit.
The latest evaluation found top-six misses; increasing the count or changing
retrieval still needs comparison on new questions.

## D10–D11: Generation, limits and evaluation

Summaries automatically use all prepared evidence in one bounded call per
attempt. Save an overview and normally 3–5 cited points, allowing 1–2 for short
sources. No manual generation, generation on reads or silent beginning-only
summary. Oversized input remains readable with an explicit summary reason.
Section summaries plus synthesis are deferred because they add calls and loss
of qualifications. Embeddings are not required for this summary path.

DeepSeek V4.1 Flash 1017 through OpenRouter/Together remains the summary route,
reasoning off with 16,384 output tokens of headroom. GPT-5.2 was selected for
answers after a limited comparison where DeepSeek failed despite useful
retrieval. Rewriting and memory reuse GPT-5.2. No universal model-quality claim
follows from these examples. Keep generation, retrieval and citation-support
evaluation separate. No autonomous-agent framework is needed for this workflow.

The existing live allowance began at $1 cumulative and now has a $0.40 document
cap shared by all paid stages. Carry spending across runtime resets. Accounting
uses fixed stage-input allowances plus maximum output reservations, then settles
observed cost. Unknown billing retains a hold; late billing can settle even when
a stale worker cannot publish. An overrun stops new admission visibly while
in-flight calls settle. These are configurable operating limits, not a
subscription model or a guaranteed absolute spending ceiling.

Context tokens measure request size; output tokens bound generation length;
dollar allowances constrain admitted paid work. Keep their configuration and
meaning separate. No adaptive output-limit retries or automatic provider fallback.

## D12–D15: APIs, interface and organization

Use cohesive feature modules with small public interfaces rather than speculative
controller/service/repository layers. Keep provider-specific types at adapters.
Version prompts/schemas in source; keep keys and deployment settings in a
commentless ignored `.env`, with a safe template and validated loaders.

React, TypeScript and Vite support a neutral, minimal shadcn/Radix interface.
Use real persisted state and bounded polling. Home offers New chat and Upload;
conversation history is separate from Runs. Shared rounded controls, DM Sans,
accessible drawers, safe Markdown and a bottom composer are accepted. Enter
sends; Shift+Enter adds a line. Follow new replies only while the reader is at
the bottom. Detailed extraction limitations remain in document/source views.

Structured logs and persisted attempts/events explain real work. Safe failures
include error type and bounded Folio code locations, excluding arbitrary
exception text, source content, secrets and local variables. Stored state is
authoritative when best-effort events have gaps. Full tracing infrastructure is
deferred. Aggregate statistics/metrics use the persisted records described below.

## D16–D18: Configuration, document reader and Runs

Development controls are a revisioned PostgreSQL singleton, seeded from env once.
Edit file/page limits, bounded parser timeout, summary enablement, token limits
and reasoning. Save with the revision read; reject stale updates. Upload starts
with one frozen snapshot used through processing, summaries and indexing.
Changes apply only to new uploads. Model, spending and worker controls remain
outside this console; development mode gates inspection, not saved-setting use.

Show content/original side by side on desktop and tabs on mobile. React-PDF uses
matching local PDF.js assets and renders one current page, with download fallback.
Activity is a drawer; repeated coverage diagnostics are bounded for readability.
Runs lists accepted uploads with separate extraction/summary/index states and
cursor pagination. Retries are attempts within a run, not extra runs.

## Conversations and history

Save ordered turns with idempotent acceptance. Titles come from the first answer
call; manual renames win over delayed generated titles. Removal hides a chat and
blocks further work/publication while retaining internal records and billing.
Separate chat workers keep long parsing jobs away from interactive execution.

Resolve follow-ups with frozen history, then retrieve fresh PDF evidence. Keep
original messages; begin background notes around 6,000 history tokens, aim for
3,000 and enforce an 8,000-token ceiling. Preserve two latest exchanges unchanged.
A before-answer fallback waits for required context work with a 600-second
deadline. Background work leaves allowance for the next question. These are
tunable limits, not lossless memory or latency guarantees.

PDF evidence and transcript references must remain distinct. Current mixed
history/document answers have an attribution defect recorded in the evaluation;
the existence of a separate transcript route does not resolve that case.

## Direct generation services

Accepted November 13: independent OpenRouter/direct OpenAI selection for answers,
rewriting and memory through a small `profile`/`generate` boundary. Canonical
model IDs and frozen endpoint/profile metadata preserve queued work. Legacy
policies without a gateway retain OpenRouter. Direct OpenAI uses the supported
GPT-5.2 snapshot; summaries/query embeddings retain their own routes. Unsupported
profiles or missing/expired credentials fail explicitly, without hidden fallback.

Direct usage times pinned rates is an estimate, distinct from provider-reported
cost. Preserve usage, cache/tier/model identity and pricing version. No external
billing reconciliation or subscription feature is included.

## November 13 verification and cleanup

The owner authorized fresh runtime data and one UI-driven conversation, with
temporary 2,000/1,000/3,000 history thresholds and the same two recent exchanges.
Restore the normal defaults afterward; keep original results and spending.
This tests one early compaction, not repeated compression or default thresholds.
The [evaluation](evaluation.md) records the actual results and unresolved defects.

Consolidate documentation around current behavior and keep historical experiments
in Git. Preserve agent guardrails, source/license pins, synthetic fixture
generation and the live Docling build context. The Humanizer skill edits prose
only; it cannot invent evidence, imply human authorship or remove real limits.

## November 14 aggregate APIs and delivery order

Finish required APIs and documentation before retrieval changes; record the video
after those improvements. Expanded recall of old conversation references is
deferred. Preserve the latest evaluation's failures rather than tuning them away.

Document statistics count current originals and active evidence. Processing
metrics cover all retained work, including removed conversations. Jobs and
attempts are separate counts: successful embedding batches are not retries.
Report measured attempt durations with sample counts; missing or reversed timing
does not become zero. Terminal error counts exclude jobs still retrying.

Use short read-only PostgreSQL snapshots, with no new state or monitoring service.
Exact totals scan retained rows; measure their cost before adding caching or
precomputed aggregates. Public OpenAPI response descriptions preserve existing
wire formats; documentation models do not add runtime validation to old routes.
