# Folio status

Updated: 2026-11-07

## Accepted direction

Folio is a general-purpose document assistant developed as public source, with a separate decision required for hosting a public service. Siddhant owns scope and design decisions; implementation uses small behavior-first vertical slices, independent review, and source walkthroughs. Reviewed, pinned skills and short durable guidance support that workflow.

The complete first ingestion slice was accepted on November 7: FastAPI, PostgreSQL, RQ/Redis, local Docker Compose and a shared artifact volume; immutable files and extraction revisions; request idempotency; durable processing intent, ownership checks and bounded retries; the schema, initial operating bounds and three test interfaces in the [system design](ingestion-system.md).

Docling processes PDF native text and English OCR. Usable partial evidence remains available with known coverage warnings. Encrypted PDFs receive a terminal unsupported-input result. DOCX and other formats are deferred. One selected PDF per conversation remains the later conversation boundary.

OpenRouter is the selected initial model gateway; GPT-6 Luna is an evaluation candidate. Exact generation/embedding models, retrieval strategy, vector storage and live-call budgets remain open. Configuration uses a commentless ignored `.env` and a safe template.

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

The accepted ingestion path and these verification exercises are implemented. Final review and the owner walkthrough still close the increment; the full document-chat product is not complete.

The [reading guide](system-design-walkthrough.md) connects the current modules to transactions, indexes, ownership and scaling. Reproduction commands belong in the [README](../README.md); parser and queue test boundaries are described in the [ingestion design](ingestion-design.md#reviewable-slices-and-agent-use).

## Next decisions and remaining scope

After the first slice's verification and owner walkthrough, agree summary/insight behavior and grounded-answer policy, then chunking, retrieval, indexing and model budgets. Summaries, chat/history, global statistics, the final document-chat demonstration/video and selected optional capabilities remain unfinished; see the [requirements ledger](requirements.md).

Noisy/rotated/handwritten OCR needs representative quality evidence. Hosting, authentication, admission backpressure, storage quotas, deletion and online artifact cleanup remain separate work. Local container persistence is not a backup or production-readiness claim.

## Handoff discipline

Record accepted decisions, checks actually run and the next unresolved question after each meaningful increment. Preserve historical evidence and distinguish implemented behavior, completed verification and proposals.
