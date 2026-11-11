# Folio status

Updated: 2026-11-12

## Accepted direction

Folio is a general-purpose document assistant developed as public source, with a separate decision required for hosting a public service. Siddhant owns scope and design decisions; implementation uses small behavior-first vertical slices, independent review, and source walkthroughs. Reviewed, pinned skills and short durable guidance support that workflow.

The complete first ingestion slice was accepted on November 7: FastAPI, PostgreSQL, RQ/Redis, local Docker Compose and a shared artifact volume; immutable files and extraction revisions; request idempotency; durable processing intent, ownership checks and bounded retries; the schema, initial operating bounds and three test interfaces in the [system design](ingestion-system.md).

Docling processes PDF native text and English OCR. Usable partial evidence remains available with known coverage warnings. Encrypted PDFs receive a terminal unsupported-input result. DOCX and other formats are deferred. One selected PDF per conversation remains the later conversation boundary.

OpenRouter is the selected initial model gateway. Automatic summaries use
DeepSeek V4.1 Flash 1017 on the explicitly selected Together standard route through
OpenRouter, with a persistent $1 deployment and owner-approved $0.40 document
allowance. This is an evaluation candidate, not a general quality guarantee. Chat/embedding models,
retrieval and vector storage remain deferred. Configuration uses a commentless
ignored `.env` and a safe template.

## Processing runs increment — November 12

The accepted header Runs link opens a separate processing-history page, leaving
the home screen and future conversations distinct. It lists one accepted upload
per row with separate extraction and summary outcomes. Cursor pagination bounds
the query and display; new uploads do not shift older pages. Retries stay inside
their request. History works outside development mode; detailed Activity remains
gated. No generic run table, reprocessing or backfill was introduced.

Activity now shows individual summary attempts, invocation/timing, reported token
usage and known versus uncertain billing. It keeps polling while summary work
continues after extraction. Ingestion and summary failures save bounded safe
exception metadata in the existing ownership-checked transaction. The shared
extractor excludes arbitrary messages, document contents, locals and paths.
Earlier failures without this metadata remain absent, rather than reconstructed.
See D18 and the [processing-runs walkthrough](processing-runs.md).

Test-first changes passed 54 focused backend checks with real isolated
PostgreSQL/Redis and controlled model responses. All 18 browser checks passed
against the Docker-served stack in 4.8 minutes. Independent review caught a null
reasoning-token value crashing Activity; the browser check reproduced it before
the guard/type fix and passed afterward. Final review found no remaining
actionable defect. Ruff, frontend types/format/build and diff checks passed.

The full Docker runtime was rebuilt and verified with five real PDF smoke inputs:
text, tables, mixed OCR, damaged and encrypted, including replay/original bytes.
An actual encrypted-PDF failure exposed saved exception locations in Activity;
those exact diagnostics survived API and worker container restarts. Desktop
light/dark and 390/320-pixel history layouts were inspected with no horizontal
overflow or page errors. Aside's browser initialization timed out, so rendered
inspection used existing Playwright tooling. Software checks paused automatic
summaries, then restored the saved preference. No new paid call occurred and the
prior cumulative spending allowance was preserved. Parser/supervision unit
suites were not rerun; the real smoke exercised the unchanged parsing path.

Current model research proposes hosted OpenAI small embeddings and a Luna answer
comparison, with a local embedding alternative. Tokenizer/pricing compatibility,
chunking, retrieval storage and answer behavior are still decisions to settle;
none was implemented or enabled by this increment. See [model notes](models.md).

## Reading workspace increment — November 11

Owner refinement: the site and Activity headers now share a fixed height, their
dividers align, and stacked document actions keep the filename's left edge.
Shared gutters also remove a mismatch between narrow-screen breakpoints. The
three-file CSS change passed independent review, type/format/build checks and
browser geometry checks at 320, 390, 700 and 1440 pixels in light/dark themes:
header bottoms matched at 60 pixels and no horizontal overflow was observed.
The backend runtime was unavailable, so these visual checks used temporary
browser-only responses against the actual frontend; no ingestion/model claim
follows and no new permanent regression suite was added for CSS values.
The web image built successfully. Full-stack availability remains unverified
at this refinement checkpoint. No application settings or model calls changed.

The accepted reading workspace now has desktop content/source columns, mobile
Content/Original tabs, an Activity drawer and compact coverage. Source jumps
preserve loaded evidence and mobile reading position; keyboard focus follows the
selected view. Status is separated from actions, and a failed extraction stays
failed even when its parser produced an intermediate partial result.

React-PDF renders one selected page with selectable text, page/zoom controls and
native open/download fallbacks. Drawing failures leave evidence usable. The
matching PDF.js worker, fonts and decoders are served locally. The lazy renderer
is about 634 kB minified (191 kB gzip), with a separate 1.27 MB worker; the build
still reports its large-chunk warning. This is an explicit cost of replacing the
native viewer, not a claim of a smaller bundle. See D17 in [decisions](decisions.md).
All 16 browser checks passed against the Docker-served app in 4.0 minutes.
Focused red-to-green checks covered compact large coverage, drawer keyboard use,
real single-page rendering, mobile focus/scroll, drawing failure and truthful
failed status. Types, formatting, Ruff and public-file checks passed. Independent
review found no remaining actionable defect. The production check caught and
fixed the PDF worker's MIME type, asset directory layout and missing-asset HTML
fallback; actual worker/font/decoder requests now succeed and missing assets
return 404. Backend parser/supervision suites were not rerun because that logic
did not change. Summary UI checks substitute responses, not model-quality proof.

The rebuilt API/web are healthy. Automatic summaries were temporarily disabled
for browser uploads, then restored while preserving a concurrent settings edit.
Recorded spending remained $0.223380304 with no held amount or new paid call.
Aside inspected a stored document on desktop and at 390 pixels: compact coverage,
original-page navigation, Activity, tab switching and readable content without
horizontal overflow. Desktop light/dark, drawer and mobile dark screenshots were
inspected; mobile drawer capture timed out. These observations supplement the deterministic
browser checks and do not establish wider document-rendering accuracy.
The [reading walkthrough](interface-walkthrough.md) explains the two workers,
data flow, failure behavior and source reading order; owner visual review remains
part of the handoff.

Known summary-preparation issue discovered during this review: repeated revision
and page diagnostics can dominate the prepared input and trigger the input
limit despite much smaller recovered prose. Diagnostic compaction needs a
separate behavior change and regression check. The evidence API also repeats
coverage metadata with every paginated response. The current UX work bounds
rendered warnings; it does not yet redesign those backend payloads.

## Development console increment — November 11

Accepted: a local development console with changes applying only to new uploads.
Seven persisted controls cover pages, file bytes, parser timeout, automatic
summaries, input/output token limits and reasoning effort. Model/provider,
execution limits and remaining spending stay read-only. The header control sits
beside the theme toggle; document inspection exposes the captured settings.
See the [console walkthrough](development-console.md).

The settings record is seeded from environment defaults once and uses a revision
check to reject stale saves. Each upload captures ingestion and summary policy
before reading multipart input. Existing work and idempotent receipts retain
their behavior; lowering the byte limit still permits verification/replay of an
already accepted original. Saved controls remain authoritative with development
mode disabled, while the console and routes disappear.

The implementation passed 80 fast backend checks (16 parser/supervision checks
excluded), Ruff and frontend type/build/format checks. Independent review fixed
summary/worker timeout incompatibility and selected-file warnings after a limit
refresh; an additional regression preserves ingestion with an unsupported
environment reasoning value. No blocking defect remained in the final source
review. All 11 browser checks passed against the Docker-served app in 3.1 minutes,
including save/conflict/upload and selected-file refresh. Existing summary UI
checks substitute summary responses; they are not model-quality evidence.
Desktop light/dark and 390-pixel console layouts were inspected without page
overflow. The rebuilt Docker stack is healthy. A real three-page PDF failed under a saved
two-page cap and succeeded on a new upload under a three-page cap; the earlier
request retained its configuration. Baseline controls were restored. No paid
calls occurred; spending remained $0.223380304 with no held amount. Parser and
supervision suites were not rerun because their implementation did not change;
the actual Docker demonstration exercised the parser with captured settings.

## DeepSeek summary increment — November 11

The owner accepted test-first response bounds and DeepSeek through OpenRouter,
with generous fixed generation headroom and no adaptive retries. Prompt/schema/
preparation versions are 6/4/3. Word targets stay soft; the schema permits a
600-character overview, 400-character points and at most eight references per
statement. Completion capacity is 16,384 tokens with reasoning explicitly off.
`SUMMARY_OUTPUT_LIMIT` is terminal and retains the known bill and usable evidence.

The native tokenizer is pinned by revision/hash, bundled with its MIT license,
and loaded offline. The selected route's missing separate prompt cap remains unknown;
financial admission conservatively reserves the full context as input plus the
configured output ceiling ($0.3342336). The local 64,000-token input bound remains.
Read-only current metadata and local tokenizer admission passed. The fast suite
passed 74 tests (16 deselected) in 17.75 seconds; Ruff and formatting passed.
Independent diff review fixed unsafe raw finish metadata and found no remaining
blocking software defect. Docker caught an incompatible transitive dependency;
constraining Hugging Face Hub to the parser image's 1.33.0 repaired the build.
The running stack is healthy and the bundled tokenizer works with networking
disabled. Fireworks became unavailable during integration; an actual mixed PDF
retained evidence and source navigation without starting a paid call. A manually
selected Together trial completed all three summaries in one paid call each,
with normal termination and zero reported reasoning tokens. The 59-page report
used 387 completion tokens and cost $0.0141951. The three new calls cost
$0.016125504; all 13 development calls total $0.223380304, confirmed by both
PostgreSQL and OpenRouter, with no held/unknown cost. The current report summary
survives reload and its page-45 citation updates original-page navigation.
Independent source review still finds citation and qualification weaknesses;
these results establish successful bounded execution, not a general quality pass.

## Earlier GPT-5.1 checkpoint — November 11

Autoloops/DeepSeek-V4.1 Flash was subsequently investigated as a lower-cost
candidate. The owner then explicitly deferred Autoloops testing or adoption and
reaffirmed OpenRouter. The owner then accepted test-first response-bound fixes
and a DeepSeek V4.1 Flash 1017 comparison through OpenRouter/Fireworks, with
generous fixed generation headroom and no adaptive retries. That comparison is
recorded above; the earlier checkpoint below remains historical. Read-only metadata for the failed NIST
call reports only 50 reasoning tokens within 4,096 completion tokens, so reasoning
exhaustion is not an established cause. No application settings, credentials or
paid usage changed during the preceding research.

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

Walk through the saved development controls and actual request snapshots with
the owner. The bounded DeepSeek comparison is complete, with the source-support
limitations recorded above; review those results before beginning grounded
answers, chunking, retrieval or indexing. Previous GPT-5.1 results remain frozen;
no document-specific prompt tuning is planned.
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
