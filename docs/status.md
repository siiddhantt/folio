# Folio status

Updated: 2026-11-11

## Accepted direction

Folio is a general-purpose document assistant developed as public source, with a separate decision required for hosting a public service. Siddhant owns scope and design decisions; implementation uses small behavior-first vertical slices, independent review, and source walkthroughs. Reviewed, pinned skills and short durable guidance support that workflow.

The complete first ingestion slice was accepted on November 7: FastAPI, PostgreSQL, RQ/Redis, local Docker Compose and a shared artifact volume; immutable files and extraction revisions; request idempotency; durable processing intent, ownership checks and bounded retries; the schema, initial operating bounds and three test interfaces in the [system design](ingestion-system.md).

Docling processes PDF native text and English OCR. Usable partial evidence remains available with known coverage warnings. Encrypted PDFs receive a terminal unsupported-input result. DOCX and other formats are deferred. One selected PDF per conversation remains the later conversation boundary.

OpenRouter is the selected initial model gateway. Automatic summaries use
GPT-5.1 temporarily on its verified OpenAI standard route, with a persistent $1
deployment and owner-approved $0.40 document allowance. GPT-5.1 retires April 1,
2027; this is an evaluation candidate, not a validated long-term choice. Chat/embedding models,
retrieval and vector storage remain deferred. Configuration uses a commentless
ignored `.env` and a safe template.

## Summary checkpoint — November 11

Autoloops/DeepSeek-V4.1 Flash was subsequently investigated as a lower-cost
candidate. Its published inference offer is suitable in principle, but hosted
limits, schema/billing details and text-LLM data terms remain unverified. The
[research notes](models.md#autoloops--deepseek-investigation--november-11) record
the proposed comparison and minimal adapter boundary. No application settings,
credentials or paid usage changed; a provider switch is not yet selected.

The automatic complete-input summary slice is implemented and independently
reviewed, with no blocking software defect found in the final review. Usable
extraction publication creates its summary intent;
workers prepare all available evidence, enforce route/token/spending bounds and
save a cited result. Oversized input stays readable with an unavailable reason.
There is no hierarchy, manual generation, generation on reads or backfill.
Prompt/schema/preparation versions are 5/3/3; reasoning is `low`. Output is a short
overview and 1–5 cited points, normally 3–5 without padding short sources; known
gaps remain visible. See the [summary contract and walkthrough](summaries.md).

The final fast suite passed 64 checks in 16.19 seconds, using real PostgreSQL
and deterministic provider clients, not live quality judgments. The checks include
red-green repairs for parent links and rejection of oversized citation lists.
Ruff checking/formatting passed for 45 files; frontend types and formatting passed.
All nine browser behaviors passed across eight initial successes and one rerun:
a concurrent evaluation upload caused the initial queue-wait timeout. Earlier
summary UI checks used real uploads with mocked summary states. Aside also
inspected the final historical summary, source-page-2 navigation, reload and a
390-pixel layout without page overflow. The unavailable-summary screen retained
evidence pagination, the original PDF and page navigation. The native PDF preview
remains tiny at narrow widths. Independent review prompted
three backend failure-path fixes, a positive margin and metadata/retry corrections.

Local generation is enabled for the ongoing evaluation; the environment template
remains disabled. Ten completed development calls, including the frozen final
NIST and unseen-document comparison, are recorded in the
[evaluation report](summary-evaluation.md). Nano failed citation support. Mini
with prompt 3/minimal improved source selection but remained verbose and weakened
optional wording. Mini prompt 4/low still failed some citation/qualification
checks; the mixed PDF passed narrow source review. The first GPT-5.1 trial improved
support but still packed too many ideas and references into points. Prompt 5
requests one central idea per point; schema 3 permits at most eight references
per statement. The frozen final report run exhausted its output allowance and
published no summary. Its second attempt ended with `SUMMARY_DOCUMENT_BUDGET`
before another paid call because a full reservation would exceed the allowance.
The unseen two-page historical document produced a saved summary. Independent
source review found three precision errors: plural relocations instead of one
move, troops placed at the cabin rather than the field, and original-log reuse
generalized across three renovations when the source established it only for
the 1930s. Two points also exceeded the 35-word prompt guidance. No substantive
parser loss explained these errors. All ten calls cost $0.20725480, matching PostgreSQL and
OpenRouter usage metadata, with no uncertain billing. The current
configuration has not established a large-document or general quality pass.

The earlier $0.3761728 Luna reservation omitted automatic cache writes. Its
verified all-write bound is $0.4683728, exceeding the accepted $0.40 cap, so no
Luna call was made. The compatible GPT-5.1 route reserves $0.38096 instead.
These are development observations, not a human-approved held-out benchmark.
The source walkthrough and the unresolved quality boundary remain owner review items.

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
- The initial OpenRouter authentication check used read-only metadata. Live generation and its explicit spending boundary were added in the summary increment recorded above.

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

The November 10 backend review grouped the workflow under `ingestion/`, retaining
shared infrastructure at the root and a stable RQ import entry for queued work.
It removed the event/ownership import cycle and fixed artifact-directory setup
errors that previously escaped the immediate failure/retry handler. A new real
database check reproduced the escaped error before the fix.

Folio process logs now have a consistent JSON envelope across the API, dispatcher
and worker, with UTC time, severity, process identity and request/attempt IDs.
Unexpected execution errors include the operation and bounded application code
locations without exception messages, document contents or machine paths.
Third-party logs retain their own formats. The saved event timeline remains the
outcome authority; diagnostic observations are not commit acknowledgments.

The final fast suite passed 23 checks against isolated PostgreSQL/Redis, including
fresh-process logging and private-message exclusion, after explicit failing tests
for the changed behaviors. Ruff and formatting passed. A separate reviewer found
no actionable defect in the final refactor/logging diff; that review was static.
The rebuilt local Docker stack passed the five-PDF HTTP smoke: native text,
tables, mixed OCR, damaged-page neighbors and expected encrypted-input failure,
plus idempotent replay and original-byte reads. Actual API/worker records shared
the same synthetic request ID through publication. The public-file/credential
check passed. No browser, full parser-quality or supervision suite was rerun for
this checkpoint; parser implementation and native supervision logic are unchanged.

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

Review the known summary failures with the owner and select the next model/configuration
decision before beginning grounded answers, chunking, retrieval or indexing.
No further tuning or paid calls are planned for this frozen checkpoint.
Chat/history, global statistics,
the final document-chat demonstration/video and selected optional capabilities
remain unfinished; see the [requirements ledger](requirements.md). The current
[summary contract](summaries.md) supersedes the earlier size-aware proposal with
automatic complete-input-only processing and bounded spending.

November 10 primary-source research compared Docling grouping, LlamaIndex
synthesizers/workflow persistence and LangGraph checkpoints. That earlier proposal
is complete input when suitable, otherwise saved section notes plus synthesis,
with one small planner and existing RQ/PostgreSQL execution. This avoids treating
a recursive synthesis helper as durable recovery. Framework adoption and exact
limits were not selected then; hierarchy remains deferred and the large-input
example does not raise the page cap.

Noisy/rotated/handwritten OCR needs representative quality evidence. Hosting, authentication, admission backpressure, storage quotas, deletion and online artifact cleanup remain separate work. Local container persistence is not a backup or production-readiness claim.

## Handoff discipline

Record accepted decisions, checks actually run and the next unresolved question after each meaningful increment. Preserve historical evidence and distinguish implemented behavior, completed verification and proposals.
