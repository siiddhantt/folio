# Folio status

Updated: 2026-11-13

## Accepted direction

Folio is a general-purpose document assistant developed as public source, with a separate decision required for hosting a public service. Siddhant owns scope and design decisions; implementation uses small behavior-first vertical slices, independent review, and source walkthroughs. Reviewed, pinned skills and short durable guidance support that workflow.

The complete first ingestion slice was accepted on November 7: FastAPI, PostgreSQL, RQ/Redis, local Docker Compose and a shared artifact volume; immutable files and extraction revisions; request idempotency; durable processing intent, ownership checks and bounded retries; the schema, initial operating bounds and three test interfaces in the [system design](ingestion-system.md).

Docling processes PDF native text and English OCR. Usable partial evidence remains available with known coverage warnings. Encrypted PDFs receive a terminal unsupported-input result. DOCX and other formats are deferred. One selected PDF per conversation remains the later conversation boundary.

OpenRouter is the selected initial model gateway. Automatic summaries use
DeepSeek V4.1 Flash 1017 on the explicitly selected Together standard route through
OpenRouter, with a persistent $1 deployment and owner-approved $0.40 document
allowance, shared with embeddings and now authorized for conversation stages too.
First-answer conversations are implemented. The owner accepted GPT-5.2 for new
answers after three independently supported examples; broader quality remains
unproven. Indexing uses Docling peer merging with heading
preservation, OpenRouter OpenAI small embeddings and PostgreSQL/pgvector. Scoped question
retrieval, saved follow-ups and hybrid memory are implemented. Configuration uses a commentless
ignored `.env` and a safe template.

## Conversation reading polish and capability audit — November 13

Follow-up refinement: sidebar selection now includes the menu area and its action
opens New conversation. Paragraph citations are inline rounded controls, spacing
is tighter, and shared radii are consistent. The composer extraction banner is
removed; known limitations remain in the source drawer and document view. Loading
feedback respects reduced motion. Reply arrival follows the bottom unless the
reader has moved back; Latest reply explicitly resumes following. Forty affected
mocked browser checks, types, formatting and the Docker web build passed.
Independent static review found no blocker. Read-only browser checks at
1440/390/320 pixels verified the selected row, inline citations, source/PDF
navigation, focus restoration and New conversation route. No backend changes
or paid calls.

The accepted polish is implemented: a compact bottom-anchored composer with
independent transcript scrolling, Enter/Shift+Enter and IME handling, safe
Markdown, five cited-passage previews and a full passage/original-page drawer.
Statement references remain explicit and turn-scoped. Shared Select, menu and
sheet components reuse the shadcn/Radix foundation; obsolete footer/menu styling
was removed. The short AI notice remains separate from known extraction gaps.

Five new behavior checks and 32 existing mocked browser cases passed across
focused runs. Types, formatting, production/Docker builds and diff checks passed.
Review caught and fixed selected-passage focus, mismatched composer/answer widths,
incomplete accessible preview names and weak Select focus indication. Real
read-only browser inspection covered saved chats, original pages, Escape/focus,
aligned edges and 1440/390/320-pixel layouts in both themes. Full screen-reader
coverage and mobile virtual-keyboard behavior were not verified. The build still
warns about the approximately 652 kB main and 634 kB PDF bundles; no size limit was
raised to suppress this. No paid model call was made.

An independent backend review passed 64 isolated conversation checks and found
one input edge: NUL/unpaired-surrogate questions could raise server errors. Two
test-first regressions now require a useful 422 without consuming the submission
key; all 14 tests in the affected conversation module and Ruff/formatting passed.
API and web images were rebuilt without resetting data.

The [capability checklist](requirements.md#capability-review--november-13)
distinguishes implemented conversations from remaining work: aggregate document
statistics/processing metrics, typed API success responses/examples, wider
summary/retrieval/follow-up and long-memory quality checks, and the final recorded
walkthrough. Filtering, streaming and multi-document chat remain optional.

## Conversation completion — November 13

The owner accepted a natural conversation workflow: separate New chat/Upload
entry, an expanding composer with a ready-document selector, generated short
titles, rename/delete and follow-up messages. Delete removes a chat from the app
and stops new publication while retaining internal records and billing. GPT-5.2
is also selected for rewriting and occasional history summaries, within the
unchanged allowance. History defaults are 6,000 trigger / roughly 3,000 target /
8,000 hard tokens, keeping two latest exchanges raw. See the [accepted checklist](conversations.md#accepted-conversation-completion--november-12).

Entry/composer and the bounded ready-document catalog are complete. Thirteen
isolated API/conversation checks and thirteen mocked browser checks passed,
along with types, formatting, build and Ruff. Independent review caught wrong
document selection after a failed lookup, late responses clearing newer drafts,
and lost acknowledged chat identities after navigation; regressions passed.
Aside verified real Home/New chat/Upload routes, the dropdown and textarea growth
from 72 to 200 pixels before internal scrolling at desktop/mobile widths, without
submitting or uploading. API/web were rebuilt; no model call was needed.

Title/rename/delete backend checks passed: 25 targeted PostgreSQL checks cover
manual-edit conflicts, generated-title fallback, deletion during paid execution,
retained unknown charges and legacy frozen policies. Migration 011 preserved the
existing document, turn and invocation hashes. API/chat worker/dispatcher were
recreated together. Aside verified rename persistence and mobile deletion using
one empty chat, without model calls. Independent review found and resolved
malformed auxiliary titles, deleted submission recovery across tabs, leaked
submission metadata in restored drafts, and acknowledged renames during failed
refreshes. Twenty-one mocked browser cases passed, with all sixteen affected
entry/management cases repeated after the final fix. TypeScript, formatting,
Ruff and builds passed. No review blockers remain. This management checkpoint
needed no paid calls.

Follow-up software is now implemented: ordered acceptance, frozen context,
versioned question resolution, fresh whole-chunk evidence, transcript references
and bounded history pages. Eighty targeted backend cases passed across focused
runs, along with 28 mocked browser cases, types, formatting, Ruff and builds.
Review found and fixed JSONB ordering changing retry prompts, metadata advancing
the submission head beyond loaded messages, lost drafts and a pagination race
that made a history gap unreachable. Migration 012 preserved existing answer,
policy, vector, input-manifest and invocation hashes.

The first real five-turn development sequence cost $0.02906768. Three answers
were source-supported; the resolver unnecessarily expanded terminology, redirected
a policy-number question without searching the PDF, and exposed an internal ID
while correctly quoting the first question. A generic resolver prompt revision
preserves old frozen instructions. Its five-turn comparison cost $0.03034205 and
fixed the observed policy-number routing and visible-ID behavior. Query expansion
remains in one rewrite despite a correct final answer; this is development-set
tuning, not a held-out benchmark. Combined follow-up usage is $0.05940973, with
$0.688830076 remaining and no held charges. See [the recorded observations](conversations.md#follow-up-development-sequence--november-13).
Hybrid memory software is complete; these short sequences do not test compaction.
Browser checks verified persistence and source/original-turn links, then exposed
a second scrollbar from a hidden input label. Its regression and the memory-wait
status check passed red-to-green; all sixteen affected chat/navigation checks,
types, formatting and build passed. Aside verified the deployed fix at desktop
and mobile widths.

Memory uses durable older-prefix jobs, a separate worker and before-claim context
preparation. Waiting consumes no chat attempt; all originals and at least two
recent exchanges remain intact. Frozen inputs, deadlines, recovery, late billing,
deletion and unchanged shared allowances are enforced. Review caught missing-key
holds, mismatched stage limits, late-ready deadline bypass, metadata omitted from
reduction checks, and blocked preparation batches; focused regressions passed.
The broad isolated suite passed 163 checks (parser/supervision excluded), followed
by 38 final memory/follow-up checks after the three batch regressions. Ruff and
format checks passed; independent review found no remaining concrete blocker.

Migration 013 preserved document, turn/result/context and invocation hashes.
All accounting participants were rebuilt with the same ledger code, and the
memory worker is listening on its separate queue. Saved live chats still read
correctly, with $0.688830076 remaining and no held charges. No paid memory call
was made and no production threshold was lowered for demonstration. Loss of
detail during repeated real compaction remains an evaluation need. Read the
[flow, failure paths and owner exercise](conversation-memory.md).

## Answer default — November 12

The owner selected GPT-5.2 through OpenRouter's `openai` route for newly accepted
questions. Application/Compose/template/local defaults agree; reasoning remains
off with 16,384 input and 4,096 output tokens. Summaries, embeddings, prompts,
retrieval, saved turn policies and the existing spending allowance are unchanged.
The selection follows the limited comparison; it does not establish general
correctness. All 46 targeted provider/conversation checks and Ruff passed.
Read-only provider metadata verified compatibility and the $0.086016 answer
reservation. Rebuilt API/chat-worker settings agree; summary/embedding settings
and the $0.748239806 remaining allowance are unchanged. No paid call was needed.

## Conversation navigation — November 12

Installed four reviewed, pinned Jakub Krehel interface skills in `.agents/skills`,
with licenses and file hashes; see [skills](skills.md). Applied them to a persistent
desktop conversation sidebar, a mobile history drawer and a quieter chat layout.
Home opens documents; Runs remains separate in the header. History reuses the
existing bounded API. Unsent drafts survive switching chats within the browser tab,
while submission replay keys retain their separate purpose. No backend, provider,
dependency or paid-usage change is part of this increment.

Test-first checks caught missing navigation, lost drafts, hidden newly created
chats, refresh failures replacing loaded history and mobile reading-position loss
after moving scrolling into the main pane. Seven fully mocked browser checks,
TypeScript, formatting and the Docker web build passed. Independent review found
no remaining blockers after the scroll fix. Browser review also identified a main
focus outline, fixed-height header overflow under enlarged text and a sticky footer
touching citation focus rings; those were refined before the final visual check.
Final browser checks confirmed the mobile reader round trip restored the exact
scroll position and the enlarged-text drawer no longer overflowed. Home, chat
and PDF layouts were inspected at 320–1440 pixels, along with keyboard focus,
source-page rendering and light/dark themes. This was not a full accessibility
audit. The PDF renderer's existing bundle-size warning remains. Spending was
unchanged; no new question or upload was submitted during this UI work.

## First saved answer — November 12

Accepted and implemented: one question per saved conversation, pinned ready index,
exact top-six retrieval, DeepSeek V4.1 Flash 1017/Together with reasoning off and
16,384/4,096 input/output allowances, separate chat worker, and unchanged shared
spending. Conversation history is now in the sidebar; Runs stays separate. The answer,
question, citations, known extraction gaps and failures survive reload. Paid-call
bookkeeping lives outside retrieval/prompt preparation. Follow-ups and the accepted
hybrid history design remain a separate increment.

Twelve chat integration checks cover scoped sources, replay/one-question boundary,
concurrent tabs, queue outage, saved checkpoints, timeout recovery, late billing,
invalid output and frozen execution limits. Independent review found current-vs-saved
worker deadline mismatch; three observed failing cases now pass with saved bounds,
lease/monitor checks and remaining-time admission. The isolated Docker suite passed
141 tests plus two subtests (supervision excluded). Existing upstream deprecations
and the PDF renderer bundle warning remain. Migration 010 preserved hashes of the
existing document, extraction, summary, 62 chunks and previous charges.

Two real manual questions used the existing public PDF; no reupload or retuning.
Retrieval found the relevant garage clause first in both runs. The first response
violated the non-answer/citation contract and remained a saved failure. The second
had valid citations but contradicted the source by saying “Yes” to whether coverage
increases the building limit, then saying it reduces that limit. Independent source
review confirmed a generation error. **The workflow is verified; answer quality has
not passed.** Do not present a ready state as semantic correctness or this model
as accepted for reliable answers. The subsequent stronger-model comparison follows.

The owner approved a GPT-5.2 comparison with unchanged prompt/retrieval/limits.
It corrected both observed failures and answered a third missing-policy-number
question with insufficient evidence. Independent source review supported all
three outputs; no general quality claim follows. Its three calls cost $0.01744647
including embeddings. All five live questions cost $0.01916217; cumulative spending
is $0.251760194 and available allowance $0.748239806, with no uncertain charge.
Aside verified saved results after reload, source-page rendering and focus return,
separate Conversations/Runs and no page overflow at 390/1440 pixels. Three mocked
chat browser checks plus the indexing regression passed, as did types/build/format
and Ruff. The owner subsequently accepted GPT-5.2 for new answers, as recorded above.
See the [data flow and reading order](conversations.md#first-answer-reading-order).

## Conversation design checkpoint — November 12

The owner requested researched question answering, saved conversations,
multi-turn context and long-history handling. The [conversation proposal](conversations.md)
maps one indexed PDF through question resolution, scoped retrieval, cited
answers and reloadable history. Primary-source research supports token-bounded
recent history plus occasional lossy memory; it does not establish a universal
standard or Folio quality. Independent review identified the shared parser queue,
15-second dispatch cycle, new paid-stage accounting, concurrent-tab ordering,
memory coverage and full-provider-ceiling reservations as concrete concerns.

Proposed: a dedicated chat worker using existing Redis, one active turn per
conversation, durable stage checkpoints, original transcripts plus versioned
memory, and explicit clarification/evidence-limit outcomes. The owner accepted
automatic history summaries and sharing the unchanged allowance across question
embeddings, rewriting, answers and memory calls. The owner also accepted after-answer precomputation with an early token trigger
and a before-request fallback. It needs a separate lightweight worker for actual
overlap, immutable-prefix/version checks, and financial admission that does not
let background reservations crowd out answers. Model/accounting and concrete
output limits remain to resolve before live use. The immediate prerequisite is
the [reservation correction](ai-budget.md), accepted as a separate test-first
increment before chat. It includes late summary billing and preserves legacy
holds. Version 2 now prices the stage input allowance plus maximum output, with
visible admission pauses on overruns. The accounting increment is complete;
conversation implementation remains next.

## Reservation and late-billing correction — November 12

New upload policies reserve the configured stage input ceiling plus unchanged
maximum output. Legacy manifests keep their old calculation. Known summary bills
settle after ownership expires without stale publication; malformed provider
responses retain valid billing metadata. Unknown calls keep their holds. Overruns
pause new summary/embedding admissions through the existing account and appear
in the development console; running calls can finish. Migration 009 adds only
that account flag, preserving all prior costs and allowances.

Test-first failures were observed for stage-sized holds, late summary charges,
overrun handling and unusable-response billing. The isolated Docker suite passed
129 tests plus two subtests; the opt-in supervision test was excluded. Ruff and
frontend type/build/format checks passed. Independent diff review found no
remaining actionable defect. The broader run exposed an unrealistic embedding
stub charge, corrected while retaining an explicit overrun case. Existing
upstream deprecation and PDF bundle-size warnings remain.

Compose was rebuilt and migration 009 applied. Before/after row hashes confirmed
the existing document, extraction, saved summary, 62 chunks/vectors and charges
were unchanged. Read-only preparation of that PDF produced a $0.0388608 new hold
versus the legacy $0.3342336, with the same 16,384 output-token maximum. No paid
model call occurred; cumulative spend remains $0.232598024 and available allowance
$0.767401976. Aside confirmed the console values and existing PDF/summary were
accessible without an unexpected pause; screenshot automation was intermittent.

## Source-linked indexing increment — November 12

The owner selected Docling HybridChunker with peer merging, heading preservation
and an initial 512-token ceiling after the [comparison](chunking-comparison.md).
The implemented [indexing slice](indexing.md) freezes this policy at upload,
creates durable intent with extraction publication, checkpoints embedding batches
and exposes only complete indexes. A bounded Activity section shows actual
attempts, progress, safe failures, model details and billing. Summary and index
failures do not remove usable extracted evidence.

OpenRouter `openai/text-embedding-3-small` is pinned to the OpenAI route with
fallbacks disabled, default 1,536 dimensions and a $0.02/M input cap. Shared
spending admission preserves the existing allowance and historical charges; the
owner explicitly approved sharing without an increase. The PostgreSQL 18 image
adds pinned pgvector 0.8.7; migration 008 preserved the existing document and
summary. This build targets Linux amd64. No approximate search index is present.

The single public FEMA October 2021 Dwelling Form was indexed without reuploading
or reparsing: 62 chunks, 16,346 reported input tokens and 62 stored vectors. Both
batches succeeded; the actual cost was $0.00032692, bringing cumulative spending
to $0.232598024 and leaving $0.767401976 with no uncertain charge. Replaying the
index request reused the same saved result. The existing 633 source elements,
31-of-32-page coverage observation and summary remain intact. The no-content
page was visually blank; its stored partial-extraction state is not rewritten.

Read-only browser inspection verified both attempt records, nonzero cost values,
reload persistence and 390-pixel wrapping without clipping. API, worker and
dispatcher restarts preserved readiness, all 62 chunks and the same two calls.
Source checks found the garage clause in chunk 10 linked to physical page 5 and
the mudflow definition in chunk 7 linked to pages 4–5. The temporary comparison
viewer was stopped after the application inspection passed.

Validation: 119 backend checks passed with real isolated PostgreSQL/Redis and
Docling, excluding the opt-in supervision test; two subtests also passed. The
focused browser regression, frontend types/build, Ruff and formatting checks
passed. Independent review found and fixed late-charge recording, lost original
failure diagnostics and unintended coupling to summary model configuration; no
remaining actionable backend finding was reported. Test cases cover queue
outage, stale ownership, timeout reservations, bounded retries, batch reuse,
source scope and combined budget admission. Live execution establishes provider
compatibility and persistence, not retrieval or answer quality.

Temporary comparison code was replaced by the maintained chunker and its tests;
observations remain in documentation, with generated reports ignored. Known
limitations: whole-element citations; unsupported source/context mappings fail
indexing rather than silently dropping content; one index per revision; no table
retrieval evaluation, reindex-generation API or general semantic-quality claim.

The [retrieval walkthrough](retrieval.md) separates implemented indexing from
next-step scoped search and cited answers. Review expected source passages before
live retrieval evaluation; the public PDF cannot validate table behavior. Keep
future automated fixtures in isolated storage so the working application stays
with one document.

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

At this earlier history checkpoint, model research proposed hosted OpenAI small
embeddings and a Luna answer comparison. The subsequent indexing acceptance and
implementation are recorded above; answer selection remains open. See [model notes](models.md).

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

Walk through the saved development controls, actual request snapshots and
indexing attempts with the owner. The bounded DeepSeek comparison is complete,
with source-support limitations recorded above; those remain relevant before
selecting grounded-answer behavior. Previous GPT-5.1 results remain frozen;
no document-specific prompt tuning is planned.
Saved chat/history and hybrid memory are now implemented through the checkpoints
at the top of this file. Aggregate document statistics and processing metrics,
complete API response documentation, the final document-chat demonstration/video
and broader quality evaluation remain unfinished; see the
[requirements ledger](requirements.md). The current
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
