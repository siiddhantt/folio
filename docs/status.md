# Folio status

Updated 2026-11-19. The local upload-to-conversation workflow is ready for a
recorded demonstration. [Requirements](requirements.md) define accepted scope;
[decisions](decisions.md) record tradeoffs and [evaluation](evaluation.md) retains
measured results, failures and costs.

## Current behavior

- Native PDF text and English OCR, immutable originals/evidence, visible known
  extraction gaps, asynchronous processing and bounded recovery.
- Automatic summaries with source references and explicit size/failure outcomes.
- Docling chunks with physical-page/source links, checkpointed embeddings and
  exact pgvector search. A conversation uses one complete, pinned document index.
- Saved conversations, generated/editable titles, ordered follow-ups and background
  history notes. Reload preserves the transcript and source references.
- Document reader, original-page navigation, automatic conversation-list refresh,
  Back controls in page headings, Runs history and Activity inspection.
- Direct OpenAI or OpenRouter model routes with captured settings and persistent
  accounting. Provider-reported costs and token-priced estimates stay distinct.
- Document statistics, aggregate processing metrics and typed public API schemas.
- Docker operation with an optional native ARM64 document worker, plus a
  [checkpointed notebook](development.md#notebook-walkthrough) for API exploration.

## Latest verification

Same-page grouping is available for a local trial. On an 11-page PDF and a
168-page book, grouped vector-six retrieved all required evidence for 12/12
positive questions, generated 12 supported complete answers and abstained on
both negative controls. Original vector-six missed one positive. Jev recovered
it with a 493 ms paired median overhead on the short PDF and added 642 ms on
the long one, where original vector-six already recovered all expected evidence.
The [comparison](evaluation.md#november-19-shortlist-and-chunk-size-comparison)
includes the 768-token and vector-twelve arms, generation failures and budget
coverage. The shipped template retains the ungrouped baseline.

### November 15 verification

Index preparation 3 includes body text nested inside pictures while preserving
provenance and excluding page furniture. Answer prompt/schema 4 allows citations
supporting partial answers and insufficient-evidence responses. Unknown source
IDs, malformed output and uncited factual answers still fail. Old accepted work
keeps its captured policies; ready indexes are immutable. The caption fix therefore
applies to newly prepared indexes.

The same two public PDFs and ten frozen questions were rerun across vector-six,
grouped vector-six, Jev on all original chunks and grouping plus Jev. Every method
retrieved 18/18 required facts and produced 8/8 complete positive answers; both
negative controls abstained. All 40 responses validated, compared with 33 before.
Independent reviewers checked actual claims and cited passages. Identical source
extraction confirmed the missing NASA caption was an indexing defect.

Sixty-four targeted software checks passed, including real database persistence
and worker checks, alongside lint and independent review. All 114 paid responses
replayed with unchanged ledgers, answers and rankings. A separate three-question
browser rehearsal verified a contextual follow-up, cited insufficient evidence,
original-page navigation and reload persistence. This is a narrow regression
set with agent-curated labels, not a general accuracy benchmark. Details and
costs are in the [fix verification](evaluation.md#november-15-caption-and-partial-answer-fix-verification).

Production remains vector-six. Grouping and Jev are experimental: all methods
tied on these questions, and NASA's entire new index fits into five groups.
Earlier single-document gains remain recorded in the
[controlled comparison](evaluation.md#november-15-controlled-retrieval-comparison).

Other completed checks cover direct-provider accounting, responsive navigation,
the ARM64 worker and the notebook. Their scope is summarized in [AI use](../AI_USAGE.md).
The native worker matched 116 package versions and nine model files, passed 58
offline checks and five HTTP upload smoke checks. The notebook's full rerun made
no POST requests and left document/job counts and spending unchanged.

## Known limitations

- Retrieval can miss table relationships and needed qualifications. Repeated
  headings can crowd useful passages; answer minimality and personal-question
  rewriting still need work. The latest successful cases do not erase earlier
  [retrieval misses](evaluation.md#november-14-retrieval-comparison).
- Mixed history/PDF answers can attach document citations to recalled user facts.
  Summary citation support and memory-note attribution also have recorded defects.
- One live history compression retained the tested facts. Repeated compression,
  hard-limit waiting and expanded recall of older exchanges remain unproven or deferred.
- Successful parsing does not establish complete extraction. OCR noise and duplicate
  no-content diagnostics remain; broader OCR quality needs evaluation.
- External evaluation charges count toward shared admission but are not included
  in ordinary application per-document totals. Old indexes keep their original
  embedding gateway, including OpenRouter.
- Screen-reader coverage, concurrent capacity, authentication, tenant isolation,
  retention and public hosting are unverified or deferred. Frontend bundle-size
  warnings remain. This is a local demonstration, not a production deployment.

## Handoff

The README and current status are condensed, with detailed evidence retained in
the linked evaluations. Release lint, formatting, typechecking and production
build passed; independent review found no blocking issue. Runtime documents,
credentials and private evaluation traces remain ignored. Git does not transfer
runtime data. Setup and isolated checks are
in [development](development.md), with the data flow and reading order in
[architecture](architecture.md).

Further quality work should address the limitations above with fresh source
questions before selecting a retrieval default. It is not a prerequisite for
recording the accepted workflow with its limits disclosed.
