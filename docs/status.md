# Folio status

Updated 2026-11-14. Working upload-to-conversation flow; quality and delivery
gaps remain. See [requirements](requirements.md), [decisions](decisions.md) and
the latest [evaluation](evaluation.md) before changing behavior.

## Working behavior

- PDF native text/English OCR, immutable originals and evidence, known-gap
  disclosure, asynchronous work, idempotency and bounded recovery.
- Automatic complete-input summaries with explicit size/failure outcomes.
- Docling chunks with headings/source links, checkpointed embeddings and scoped
  exact pgvector retrieval. Only complete indexes are ready for chat.
- Saved conversations, generated/renamed titles, retained-record removal,
  ordered follow-ups and background history notes with a bounded waiting path.
- Minimal document/chat UI, original-page navigation, cited passages, separate
  Runs history, Activity inspection and saved controls for new uploads.
- Independent direct OpenAI/OpenRouter generation settings; frozen profiles and
  shared persistent accounting with known, estimated and uncertain usage.
- Document statistics and aggregate processing metrics, with typed public
  success-response OpenAPI schemas and examples.

## Latest verification

The release pass fixed standalone pytest imports, packaged notebook helpers in
the verification image and excluded runtime outputs from build contexts. That
image built successfully after a package-download timeout; all 45 affected
checks passed inside it without mounting the workspace. The 21 host checks are
an overlapping subset, not extra coverage. Compose platforms, notebook syntax,
cleared outputs, documentation links and secret-sensitive paths passed. An
independent review checked Mac setup and the notebook's explanations against
the implementation. No paid model calls were made in this release pass.

The API notebook completed a real upload-to-answer run and a complete rerun.
All 14 code cells finished; rerun made no POSTs and left document/job counts and
spending unchanged. Its saved receipts, source links, attempts, usage and worker
logs are under ignored `output/demo/folio/`. The earlier interrupted/failed run
remains under `output/demo/epa-radon/`; no history was overwritten.

The fresh EPA guide exposed two source-mapping bugs: attached figure footnotes
and structured contents tables. Both were reproduced test-first and fixed with
versioned preparation/normalization. New uploads capture normalization 2;
accepted version-1 work retains its behavior. All 24 parser/chunking checks and
19 configuration/retrieval/checkpoint checks passed, plus the earlier two chat
workflow checks. Independent reviews found no blocking code defects. Ruff,
formatting, cleared notebook outputs, Docker builds and secret-path checks passed.

The source produced 788 elements and 78 indexed chunks. On 24 independently
labeled required facts, vector6 supplied 19, vector12 supplied 21 and hybrid6
supplied 17. No method recovered the complete two-test table. Production remains
vector6; the experimental hybrid selector is not a routing option. See the
[evaluation](evaluation.md#november-14-retrieval-comparison) for exact methods,
held-out results, timing and input-cost limits.

Ten questions stayed in one conversation: eight answers with supported claims,
including three incomplete responses, and two explicit output-validation
failures. The latter rejected citations on non-answer outcomes; one rewrite also
changed a personal-values question toward generic guidance. No hidden retry or
alternative answer replaced these results. New-run cost was $0.10113222; the
shared allowance has $0.406827606 remaining with no holds. Normal history limits
were unchanged, and this run did not trigger compression.

Required document statistics, processing metrics and public OpenAPI schemas
remain implemented. The prior API slice passed 121 affected checks and real
HTTP/payload inspection; its details remain in Git. Folio is running locally,
with persistent Docker volumes and the two real EPA runs.

### Previous live evaluation

One new 56-page DOE guide was uploaded through the frontend after an authorized
data reset. Prior spending was carried forward. All twelve questions stayed in
one chat. Extraction, summary, all 120 indexed chunks and all terminal turns
persisted; reload retained the transcript and sources.

One real background compression used temporary 2,000/1,000/3,000 thresholds.
The final turn used notes, retained five early facts and the heat-pump correction,
and used 1,454 history tokens instead of 2,185. Normal 6,000/3,000/8,000 defaults
were restored; original turns and test-policy snapshots were preserved at that
checkpoint. Their local evaluation exports survive the later Docker data loss.

Accounted usage for that run was $0.15188424, including direct token estimates,
with no unknown billing or outstanding holds. Median server completion time was
8.86 seconds. This sequential development run is not a load/accuracy benchmark.

Earlier checkpoints passed 171 affected backend checks and 40 controlled browser
checks. The November 13 cleanup consolidated documentation into one README and
seven guides, preserving agent guardrails and historical evidence in Git.
Current software checks and live model quality remain separate evidence.

## Demo handoff

Feature work is frozen for the current demonstration. Run the Mac smoke test,
record the working workflow and disclose the measured limits. Further retrieval
and answer-quality work can follow review; it is no longer a prerequisite for
recording this version. Production retrieval remains vector6.

The root temporary folder was moved intact into ignored `output/archived-tmp/`.
Runtime records, current evaluation artifacts and private settings remain intact.
Compose explicitly targets Linux amd64; Apple Silicon uses emulation, which
still needs validation on the actual Mac. Fresh databases use the remaining
agreed allowance and new notebook checkpoints; Git does not transfer runtime data.
The notebook explains the background work beside its existing executable cells.

Follow-up defects remain: non-answer citation validation, personal-question
rewriting, the two-test-table retrieval miss and omitted supplied qualifications.
The wider retrieval comparison is evidence for a future decision, not a default
change or a claim of improved generated answers.

The owner accepted the notebook, source questions and test surfaces. It exposes
real requests and stored work; existing routes do not manually execute every
processing stage. Runtime outputs, exact comparison inputs, independent labels
and review notes remain ignored. Optional notebook dependencies do not change
application image dependencies.

Mixed history/PDF attribution remains a known defect: document-answer citations
can be attached to recalled user facts. Expanded old-transcript recall is
deferred. Memory-note attribution, repeated compaction and hard-limit waiting
remain limitations. Summary citation quality improved on this source but earlier
failures are not erased. No general quality claim follows from one PDF.

Current extraction diagnostics can duplicate no-content pages; bundle-size
warnings remain unsuppressed. Broader OCR/held-out quality, concurrent capacity,
authentication, retention and hosted operation remain unproven or deferred.
This release is prepared for demonstration and review. No public deployment is implied.
