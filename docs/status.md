# Folio status

Updated 2026-11-13. Working upload-to-conversation flow; quality and delivery
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

## Latest verification

One new 56-page DOE guide was uploaded through the frontend after an authorized
data reset. Prior spending was carried forward. All twelve questions stayed in
one chat. Extraction, summary, all 120 indexed chunks and all terminal turns
persisted; reload retained the transcript and sources.

One real background compression used temporary 2,000/1,000/3,000 thresholds.
The final turn used notes, retained five early facts and the heat-pump correction,
and used 1,454 history tokens instead of 2,185. Normal 6,000/3,000/8,000 defaults
were restored; original turns and test-policy snapshots remain intact.

Accounted usage for that run was $0.15188424, including direct token estimates,
with no unknown billing or outstanding holds. Median server completion time was
8.86 seconds. This sequential development run is not a load/accuracy benchmark.

Earlier implementation checks at `1c793a9` passed 171 affected backend tests,
Ruff, formatting, frontend types and Docker builds. Prior UI polish passed 40
affected controlled browser checks. Those are historical checkpoints, not tests
rerun by the documentation cleanup. Live model results are evaluated separately.

Documentation now has one README and seven focused guides. The live Docling
build context and synthetic fixture generator moved to maintained locations;
obsolete experiment files/walkthroughs remain available in Git history. Agent
guardrails and upstream licenses are retained. The relocated parser image built;
two normalization checks, Ruff/formatting and twelve-document link checks passed.
The generator CLI loaded in the existing offline verification image. Independent
review found and resolved generator lint/setup regressions. No application or
prompt behavior changed; no broad database/browser suite was rerun for prose.

## Next work, in order

1. Correct mixed history/PDF attribution: the current document-answer contract
   forces a PDF citation onto a statement recalling user facts. Add a focused
   regression before changing that contract; preserve source-scope validation.
2. Compare retrieval coverage on new questions. Relevant passages ranked just
   outside the top six for savings, upkeep and table qualifications. Do not treat
   parser success or an honest abstention as a successful customer outcome.
3. Tighten memory-note turn attribution, summary citation coverage and handling
   of personalized facts absent from the PDF. Repeated compression and the
   hard-limit waiting path still need live evaluation.
4. Finish R09 document statistics, R10 aggregate processing metrics, typed
   success-response OpenAPI schemas/examples and the recorded demonstration.

The first item is the recommended next slice, not an accepted expansion of
scope. No hidden tuning was used to replace failures in the latest evaluation.
Current extraction diagnostics can duplicate no-content pages; bundle-size
warnings remain unsuppressed. Broader OCR/held-out quality, concurrent capacity,
authentication, retention and hosted operation remain unproven or deferred.

The source branch is prepared for review; no merge or public deployment is
implied. Keep runtime uploads, raw traces, credentials and machine settings out
of tracked source.
