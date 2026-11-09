# Folio status

Updated: 2026-11-09

## Accepted direction

Folio is a general-purpose document assistant developed as public source, with a separate decision required for hosting a public service. Siddhant owns scope and design decisions; implementation uses small behavior-first vertical slices, independent review, and source walkthroughs. Reviewed, pinned skills and short durable guidance support that workflow.

The complete first ingestion slice was accepted on November 7: FastAPI, PostgreSQL, RQ/Redis, local Docker Compose and a shared artifact volume; immutable files and extraction revisions; request idempotency; durable processing intent, ownership checks and bounded retries; the schema, initial operating bounds and three test interfaces in the [system design](ingestion-system.md).

Docling processes PDF native text and English OCR. Usable partial evidence remains available with known coverage warnings. Encrypted PDFs receive a terminal unsupported-input result. DOCX and other formats are deferred. One selected PDF per conversation remains the later conversation boundary.

OpenRouter is the selected initial model gateway; GPT-6 Luna is an evaluation candidate. Exact generation/embedding models, retrieval strategy, vector storage and live-call budgets remain open. Configuration uses a commentless ignored `.env` and a safe template.

Accepted November 9: a minimal upload/document-detail/source interface with React,
TypeScript and Vite; light/dark typography; reusable feature components; and a
server-gated development view of actual processing history. The [interface contract](interface.md)
defines the scope. Runtime screens contain no built-in sample documents or simulated outcomes.
The owner refined the visual direction to customized shadcn controls, neutral
light/dark surfaces, a single sans-serif family and minimal visible copy.
The owner reviewed the revised interface and approved that visual direction on
November 9. The implementation checkpoint is committed and pushed in
[the interface review](https://github.com/siiddhantt/folio/pull/1); the review is
still a draft. This does not settle the later summary/retrieval decisions.

## Implemented and checked

- Requirements, staged decisions, pinned skill provenance and AI-use history are recorded. The source repository is [siiddhantt/folio](https://github.com/siiddhantt/folio).
- The offline Docling/LiteParse comparison ran six synthetic fixtures three times per engine. Both preserved expected text/OCR facts; Docling preserved stronger table structure. Both missed corruption as a structured error. See [measured results and limitations](ingestion.md#results).
- The application now accepts PDFs, persists originals and work, dispatches and claims attempts, publishes page/table evidence, and exposes status, original bytes and paginated evidence. Recovery, retry and stale-owner checks exist in [src/folio](../src/folio).
- The combined Docker suite passed 27 checks: 12 against real PostgreSQL/Redis and 15 offline parser checks, including real text, tables, OCR, damaged/empty/encrypted PDFs and controlled export failures. The opt-in supervision probe was separate. These are bounded contract checks, not general parser-accuracy claims.
- The full Docker HTTP smoke passed for five PDFs: text, table, mixed text/OCR, damaged and encrypted. It also checked idempotent replay and original-byte retrieval. The encrypted case ended in the expected terminal error; a no-content page retained an unknown-cause warning.
- OpenRouter authentication was checked using read-only metadata. No inference call, model-quality result or application spending budget is implied.

## Operational verification

[The recovery exercise](../scripts/check_recovery.py) passed acceptance while Redis was stopped and processing after restart. Two actual workers overlapped, confirmed by persisted attempt timestamps. Killing an active worker with SIGKILL produced one `WORKER_LOST` attempt followed by one successful retry. The exercise advanced only its synthetic attempt's lease deadline; it did not wait through the default seven-minute lease. The normal one-worker setup was restored.

[The native-hang probe](../tests/test_supervision.py) passed in 60.639 seconds with a one-second job timeout and one-second monitor interval. It verified the parent's kill path and disappearance of the workhorse and its same-process-group child. This tests supervision behavior with shortened settings, not the default 300-second timeout or every possible native failure.

The accepted ingestion path, independent implementation review and these verification exercises are complete. A fresh focused source review on November 9 found no blocking defect for a minimal local upload/status/evidence interface. It inspected the current ingestion contracts, implementation, tests and final index change; it did not rerun the suites. Docker's engine was unavailable during that checkpoint, so no fresh runtime result is claimed. The owner walkthrough still closes the increment; the full document-chat product is not complete.

Current observability includes durable attempt history, timestamps, errors, parser duration,
evidence/coverage diagnostics and recorded lifecycle/stage events. A default-off development
endpoint exposes safe configuration and identity metadata. API and fresh worker processes
configure correlated application logging explicitly. Recorded observations can have gaps;
there is no reliable page-level progress or distributed tracing collector. PostgreSQL-backed
request status owns the product outcome: an RQ execution can finish normally after recording
an extraction failure.

The [reading guide](system-design-walkthrough.md) connects the current modules to transactions, indexes, ownership and scaling. Reproduction commands belong in the [README](../README.md); parser and queue test boundaries are described in the [ingestion design](ingestion-design.md#reviewable-slices-and-agent-use).

## Next decisions and remaining scope

The accepted minimal interface is implemented and checked in the local Docker stack.
It shows actual processing/retry outcomes, extracted text/tables, known gaps and source-page
links. A durable document URL survives reload. Embedded PDF preview loads after usable
extraction; open/download remain available throughout. A document library is not included.
The [hands-on walkthrough](interface-walkthrough.md) follows a chosen PDF through the UI,
Network panel and persisted execution history.

The November 9 interface increment passed 21 fast backend checks against isolated
PostgreSQL/Redis services and seven browser checks against the Docker-served app.
Browser checks cover upload/reload, partial coverage, table/source links, real
stage history, diagnostic resilience, uncertain-response replay and a narrow
encrypted-PDF failure screen with persisted theme. The diagnostic check injects
a response shape; it is not a parser-quality evaluation. Existing parser and
supervision suites were not rerun because their implementation did not change.
Type checking, production builds, formatting and the public-file check passed.

Independent review corrected a dispatch timestamp that changed without a new
enqueue, code-less diagnostic handling, and an unsupported queue-recovery label.
A subprocess check caught suppressed lifecycle logs in fresh API/worker processes.
The browser checks also led to gating embedded preview on successful extraction;
an encrypted native viewer had interfered with narrow-screen interaction.

After the visual revision, all seven browser checks passed again. A manually
uploaded public nine-page technical report was accepted with the worker stopped,
then processed successfully after its normal restart. The UI exposed real events,
loaded a second evidence page and updated the original-page link. This validates
the workflow, not the semantic accuracy of all extracted content. Native PDF
rendering varies by browser; page pixels were not validated in the in-app viewer,
and open/download actions remain available. Normal worker operation was restored.

Then agree summary/insight behavior and grounded-answer policy, followed by chunking, retrieval, indexing and model budgets. Summaries, chat/history, global statistics, the final document-chat demonstration/video and selected optional capabilities remain unfinished; see the [requirements ledger](requirements.md).

Current discussion: [a size-aware summary slice](summaries.md), with source-linked
preparation before model calls, complete-input or hierarchical processing, and
saved-result reuse. This remains a proposal. Trigger, output format, provider
route, quality thresholds and spending limits are not selected. No summary or
embedding implementation or live model evaluation has begun.

Noisy/rotated/handwritten OCR needs representative quality evidence. Hosting, authentication, admission backpressure, storage quotas, deletion and online artifact cleanup remain separate work. Local container persistence is not a backup or production-readiness claim.

## Handoff discipline

Record accepted decisions, checks actually run and the next unresolved question after each meaningful increment. Preserve historical evidence and distinguish implemented behavior, completed verification and proposals.
