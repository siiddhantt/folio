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

November 19 local trial: new uploads may opt into grouping adjacent complete
chunks only when all linked sources occupy the same physical page and the
combined text fits the existing token limit. This preserves source IDs and
embeds the joined text once. Local manual testing uses grouped vector-six.
The checked-in defaults retain the original baseline. A wider prompt recovered
the known miss with more evidence tokens, and the Jev shortlist recovered it
with an extra provider call. None recovered additional facts on the 168-page
test. See the [comparison and its limits](evaluation.md#november-19-shortlist-and-chunk-size-comparison).

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

## November 15 direct OpenAI document stages

Direct OpenAI is accepted for summaries and document/query embeddings as well
as answers, rewriting and memory. Reuse the existing generation boundary for
GPT-5.2 summaries; retain text-embedding-3-small and 1,536 dimensions for direct
embeddings. Freeze gateway/profile metadata with new work. Older accepted runs
and indexes keep their original route, including query vectors for those indexes;
there is no automatic credential fallback or rewrite of stored index policies.
Token-priced costs remain estimates and preserve unknown usage reservations.

The local setup selects direct OpenAI for new work and limits summary output to
4,096 tokens within the existing shared spending allowance. Grouped env comments
are accepted for readability. This provider change is not a retrieval-quality
fix: repeated page furniture can dominate nearest-neighbor results, and non-answer
citation validation remains a separate known defect.

## November 15 controlled retrieval experiments

Compare better chunk grouping and reranking independently before changing the
default. Use one reproducible script with frozen source expectations, original
query vectors where available, and the same answer prompt/model across evidence
arms. The first chunking candidate merges adjacent whole chunks on the same
physical page within 512 tokens, preserving text and provenance. The separate
reranking candidate scores every original chunk with a pinned local MiniLM
cross-encoder, then supplies six. Sliding windows preserve long passages during
scoring. Correct-source generation separately tests whether the answer model can
use the missing evidence. Neither method is accepted as a production default.

Record preparation, model loading, warmed scoring and generation timings
separately. Start with independently source-checked development and held-out
questions from the same document, plus an unanswerable control; these do not
establish cross-document quality. Keep private sources, labels and answers ignored.
The first run has a $0.12 envelope within the existing shared/document allowances.
A separate durable evaluation ledger reserves that envelope against the live
allowance and carries actual or uncertain charges forward without fabricating
application turns. Interrupted accounting and uncertain calls fail closed;
completed paid calls are replayed from saved responses.

The follow-up accepts a separate Jev reranking experiment using the same frozen
questions and original chunks. Use `jev-1.14.0` through TypeSafe, with one batched
request per query: the shared state contains only the query, and each independent
Score question contains its own candidate passage. Rank by the common relevance
rubric, retain six original passages, and use the existing GPT-5.2 answer prompt.
The trial's envelope is $0.08 within the remaining allowance. A TypeSafe key is
optional local configuration; the public template contains no value. This is
an evaluation path, not an accepted production provider or retrieval default.

The next accepted trial compares original vector-six, grouped vector-six, Jev on
all original chunks, and Jev on all grouped chunks across two fresh public PDFs.
Freeze independently source-checked questions before inspecting retrieval, keep
extraction misses in the denominator, and use the same first-turn answer prompt
and pinned generation policy across all four arms. Generate an answer for every
question/arm, including each document's unanswerable control. Three alternating
Jev samples measure latency and ranking variability; the first sample determines
answer evidence. Query embeddings are measured once per question and shared by
both vector arms. Record final input tokens as well as retrieval and answer
quality, since a six-passage limit does not equalize evidence volume.

Use the same single-file runner and separate ignored ledgers, with at most $0.18
reserved per new document within the remaining shared/document allowance. Normal
upload summaries and original index embeddings retain application accounting.
Cache exact completed responses, fingerprint imported prompt/provider code, and
preserve incomplete outcomes without replacement calls. This mode is restricted
to fresh documents or an exact replay of their existing experiment directory.
It does not change the production retrieval default.

## November 15 evidence coverage and partial-answer fixes

The owner accepted two narrow fixes before selecting a retrieval default.
New chunk preparation includes extracted BODY text nested within figures in
both serialization and provenance traversal. Actual page furniture stays
excluded; no OCR or generated caption service is added. New indexing policies
capture preparation version 3. Existing accepted policies without that field
retain version 2, and ready indexes remain immutable.

New answer prompt/contract version 4 permits source-scoped citations on
`insufficient_evidence` and clarification responses. Supported partial facts
should stay visible alongside a clear statement of what the supplied evidence
cannot establish. Every nonempty citation must still identify a supplied
passage; ordinary factual answers still require citations. Existing accepted
turns retain their captured prompt/validation behavior. This relaxes an outcome
restriction without treating a valid ID as proof of semantic support.

Rerun the frozen two-PDF questions against fresh uploads with the corrected
index policy, preserving old traces and expected facts. The four comparison
arms and generation model/output limit remain fixed; the current prompt and
validation versions are recorded explicitly. Use at most $0.15 per experiment
within the remaining allowance, plus normal ingestion and a short live demo
rehearsal. Check the actual user flow before proposing recording steps. Neither
fix selects grouping or Jev as the production default.

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

## November 14 retrieval comparison and walkthrough

Compare the current top-six retrieval with wider and hybrid retrieval on a fresh
PDF and new source-checked questions before selecting a new default. Separate
evidence coverage from generated-answer support, latency and input cost. Keep
the source, chunks and question embeddings fixed across methods; a comparison
does not authorize promoting its winner automatically.

The owner selected a Python notebook for the connected API walkthrough, with
visible code and ordered cells rather than a CLI. Reuse existing HTTP routes and
save local receipts/results under ignored `output/`. Upload starts background
summary/index work automatically; later cells observe those stages. Rerunning a
cell must preserve its original request intent rather than create duplicate work.
The owner accepted the EPA guide and ten source-checked questions, including
three held out. Compare vector6, vector12 and hybrid6 (vector12 plus English
keyword12, equal reciprocal-rank fusion with constant 60). Freeze that rule
before seeing results; use no extra model call for keyword selection/reranking.
First measure evidence coverage, timing and prepared input cost, without claiming
these measurements alone prove improved generated answers. The accepted test
surfaces are the notebook HTTP/checkpoint helper and the retrieval selector with
real PostgreSQL. Existing workflow checks still guard publication and token fitting.

The fresh source exposed two source-mapping defects before embedding: attached
figure footnotes were missing their active heading context, and structured
`document_index` tables were omitted during normalization. Chunk preparation 2
maps attached footnotes; normalization 2 retains those tables with their cells
and locations. New uploads capture version 2; accepted version-1 requests keep
their behavior. Existing failed runs remain intact. Neither fix relaxes source
validation or adds an index-retry API.

## November 14 release boundary

Freeze feature work and prepare the current workflow for demonstration and review.
Further retrieval changes and the recorded answer-quality defects are follow-up
work, not prerequisites for recording this version. Keep those limits visible;
do not present selected successful examples as a general accuracy claim.

At this checkpoint, keep the supported image architecture explicit as Linux amd64, including on
Apple Silicon through Docker Desktop emulation. Native ARM dependency work is
deferred (superseded for the document worker by the November 15 decision below).
Verify the actual Mac before recording; Windows/Linux results do not
establish Mac performance. Fresh installations preserve the agreed cumulative
spending boundary rather than silently receiving a new allowance.

## November 15 native document worker

Native ARM64 document processing is accepted after the emulated Mac worker hit
its parser time limit. Rebuild Folio's existing worker with ARM64 CPU wheels,
keeping the pinned Docling/PyTorch versions, model revisions, parser settings,
queue contract and persisted data. Use an optional Compose overlay and a separate
image tag; other services retain their existing architecture. The original amd64
build remains available.

[Upstream Docling](https://docling-project.github.io/docling/getting_started/installation/)
supports ARM64, and [PyTorch](https://download.pytorch.org/whl/cpu/torch/)
publishes matching CPU wheels.
Continuing emulation with longer timeouts would retain its performance cost;
adopting Docling Serve would add a service/API boundary that this workflow does
not need. Native CPU execution is selected; host Metal/GPU execution and a full
stack architecture migration remain outside this change. Validate extraction,
OCR, table/source mapping and failure handling before switching the running
worker. Architecture support alone is not a speed or extraction-quality result.

## November 15 navigation polish

Keep the neutral interface and existing New chat/Upload actions, with a larger
home headline and short explanation of the document workflow. Remove the repeated
sidebar heading, manual history refresh and the empty-document sentence beneath
the new-chat composer. Keep loading, failure and retry feedback.

Refresh conversation history after local changes, on focus/visibility return,
and 15 seconds after each completed read while the tab is visible. Preserve the
current list and error recovery control through failed background reads. Back sits
beside each page's content heading, outside the global navbar. Its shared behavior
returns to the previous in-app history entry, including after a reload; a direct
visit falls back to Home. Keep it available during document loading/failures, with
page actions wrapping where needed on narrow screens.
