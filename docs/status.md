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

The aggregate API slice adds read-only database snapshots across five stages.
Tests cover upload replay, current originals, page observations, retries,
successful index batches, retained chat work and missing/reversed timing.
Independent code reviews found no blocking defects; suggested timing and retained
history regressions were added. All 121 affected backend checks passed: 116 on the
host and five indexing checks in the required Docling image after an initial
host-only setup failure. The ten focused aggregate/schema checks also passed
after fixture isolation. Nineteen saved real public payloads matched the response
models. Ruff, formatting, documentation links and Docker builds passed.

Both new endpoints were checked over real HTTP. PostgreSQL's health probe now
waits for TCP readiness; a controlled fresh-database check verified that its
socket-only initialization phase does not start migrations early. No model calls
were made. These checks establish software behavior, not improved answer quality.

The Docker engine had no main application containers or volumes at the start of
runtime verification. Rebuilds do not recover the earlier PDF/chat database.
The full stack is rebuilt with an empty library and the previous remaining
allowance carried forward. Saved local traces and the tracked quality report
remain available; no synthetic customer history was inserted.

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

## Next work, in order

1. Compare retrieval coverage on new questions. Relevant passages ranked just
   outside the top six for savings, upkeep and table qualifications. Do not treat
   parser success or an honest abstention as a successful customer outcome.
2. Record the working demonstration after retrieval improvements, as selected.
3. Reassess summary citation support and missing personalized facts during quality
   review. Memory-note attribution, repeated compaction and hard-limit waiting
   remain limitations; expanding old-transcript recall is deferred.

Mixed history/PDF attribution is a known defect: the current document-answer
contract can attach a PDF source to recalled user facts. It remains recorded,
without expanding this slice into transcript search. No hidden tuning replaced
failures in the latest evaluation.
Current extraction diagnostics can duplicate no-content pages; bundle-size
warnings remain unsuppressed. Broader OCR/held-out quality, concurrent capacity,
authentication, retention and hosted operation remain unproven or deferred.

The source branch is prepared for review; no merge or public deployment is
implied. Keep runtime uploads, raw traces, credentials and machine settings out
of tracked source.
