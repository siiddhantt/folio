# From one PDF to a cited answer

November 12, 2026. **Chunking, embeddings and pgvector storage are accepted and
implemented; question retrieval and answers are the next increments.** The
[indexing guide](indexing.md) describes the working behavior. D03 fixes one-PDF
conversation scope; D08 and the answer parts of D10 still need their concrete
contracts before implementation. The [offline comparison](chunking-comparison.md)
informed the selected Docling merging and heading preservation.

## Follow a concrete question

The public [FEMA Dwelling Form, October 2021](https://www.fema.gov/sites/default/files/documents/fema_F-122-Dwelling-SFIP_2021.pdf)
provides a working example. The inspected file has 32 physical PDF pages,
393,573 bytes and SHA-256
`4e91d6417cba13c18d4402083a0c02811da8264be6fcb8557c6afa4f8b6e2e74`.
Its extraction produced 633 source elements and no tables. Physical page 2
reported no recovered content and was visually blank; that observation does not
make every unextracted page blank or establish complete extraction accuracy.

Ask: “How much coverage can apply to a detached garage?” Physical page 5 connects
the 10% limit to a reduction in the building coverage available, with exclusions
for residential, business and farming use. An answer preserving only “10%” loses
essential qualifications.

The complete path, with the first line now implemented, is:

```text
immutable extraction → source-linked chunks → saved vectors → ready index
question → compatible query vector → scoped passages → answer + citations
```

**Chunking** groups extracted material into pieces small enough to search and
send to a model. Preserve the garage clause together where possible. FEMA's
mudflow definition crosses physical pages 4–5: page boundaries alone are poor
meaning boundaries. Larger pieces retain context but consume more tokens and
can include distracting material. Overlap repeats context and cost.

The selected Docling HybridChunker uses peer merging and heading preservation,
starting at 512 tokens including repeated heading context. The production checks
validate submitted text and its source mapping. No overlap or second custom
splitting engine is added. Source links identify whole original elements, not
precise fragment highlights. See the [comparison](chunking-comparison.md) and
[upstream contract](https://docling-project.github.io/docling/concepts/chunking/).

**An embedding** represents a passage as numbers used to compare similarity.
The selected model is OpenRouter's `openai/text-embedding-3-small` at its default
1,536 dimensions; specifications and alternatives are in [models](models.md).
Similar vectors suggest related meaning, not factual support. Save the exact
submitted text and hash. Freeze model, dimensions, tokenizer, rendering and
chunking policy with the revision. Questions must use that same
embedding space; matching vector lengths alone do not establish compatibility.

**Retrieval** embeds the question and compares it with chunks from the permitted
revision/index only. Exact pgvector search inside PostgreSQL is the accepted
starting point for the next increment. A lexical baseline can reveal misses involving exact words,
identifiers or numbers. Compare both before adding fusion or reranking.
The [pgvector contract](https://github.com/pgvector/pgvector) supports exact search
and ordinary scope filters. Its cosine-distance operator returns smaller values
for closer vectors; the value is not an answer-confidence percentage.

**Generation** receives the question, selected evidence and known gaps. Its model
is a separate choice: Luna is an unselected candidate requiring compatibility
and quality checks. Proposed outcomes are a cited answer, clarification, or an
explicit evidence limitation. Validate references against supplied evidence;
separately review whether it supports every claim. A retrieval miss cannot prove
the original lacks an answer. Document instructions remain data, and earlier
answers cannot become independent evidence.

## Preserve evidence and keep storage small

The existing [schema](../src/folio/migrations/001_ingestion.sql) stores immutable
`extraction_revisions`, `source_pages`, `source_elements` and `element_locations`.
Tables live in `source_elements.table_data` with cell relationships. The
[parser](../src/folio/ingestion/parsing/parser.py) preserves Docling references in
`provider_ref`; its locations currently describe source elements, not verified
character offsets or individual table-cell page boxes.

Chunk metadata can refer to a whole source item even after splitting it. Map
references to stored elements within the revision; do not invent finer locations.
Unlocated raw content is not citeable normalized evidence. Record unmapped or
excluded material explicitly. Context headings and repeated table headers need
their own source links too.

| Record | Responsibility |
| --- | --- |
| Retrieval index | Revision, frozen policy, expected chunks, coverage, durable state and ownership. |
| Chunk | Index, stable order, exact embedding text/hash and one vector. |
| Chunk source | Ordered links to existing revision/element identities; precise ranges only when verified. |
| Batch and invocation | Stable submitted membership, attempts, completion, reservation and observed/unknown billing. |
| Conversation and question outcome (not implemented) | Pinned revision/index, question, supplied evidence, answer/citations or failure, and replay identity. |

Database relationships reject cross-revision links. Current storage supports
one index per revision. A later model/policy replacement needs an explicit new
index-generation design; changing settings does not mutate saved vectors. No extra page-text store, provider registry or
multiple-vector abstraction is needed initially.

A regular database index on the retrieval-index identifier narrows work to one
document's chunks. Exact vector search then compares those candidates. An
approximate vector index is a separate optimization that trades some recall for
speed; defer it until measured scoped latency warrants comparison. Exact nearest
vectors still need not contain the answer. Measure chunk count, query latency,
resource use and expected-evidence retrieval before claiming capacity.

## Make recovery part of the outcome

The existing example received **one explicit first indexing intent** for its
saved revision, without reparse, reupload or backfill. New enabled uploads freeze
the indexing policy on receipt; extraction publication creates their index intent.

PostgreSQL owns that intent; Redis delivers work. A short transaction claims work
with a token and expiring lease: permission for this worker to update the result
until a deadline. External calls run outside database transactions. Each bounded
batch is validated and saved under current ownership. Successful batches survive
retry. One final transaction publishes the index only when all planned eligible
vectors exist; partially built indexes remain hidden. Extraction gaps and any
declared indexing exclusions remain visible.

| Failure | Observable result (answer behavior remains proposed) |
| --- | --- |
| Duplicate delivery or stale worker | No duplicate publication; ownership checks reject stale updates. |
| Worker stops between batches | Resume missing work within the frozen policy. |
| Redis unavailable | Saved intent remains pending for redispatch. |
| Wrong model, vector shape or response mapping | Reject the response and retain billing observations. |
| Provider times out, or database fails after response | No assumed success; retain uncertain reservation and bound retries. |
| Index incomplete or budget exhausted | Explain unavailability; reading and existing summaries remain usable. |
| Missing, ambiguous or conflicting evidence | Return the agreed limitation/clarification or attributed conflict. |

Shared spending admission now counts summary attempts and embedding invocations.
The owner approved sharing the existing $1 cumulative and $0.40 document caps
without an increase. Query/answer execution remains a later increment; its paid
validation needs an explicit scope within the remaining allowance. Reserve before transmission; unknown billing
retains its reservation. A retried call may be charged again. Replay protection
cannot promise exactly-once provider execution.

## One complete increment, small passing checkpoints

The next complete outcome is **one indexed PDF → one question → inspect returned
passages and source pages**. Then add one saved cited answer or limitation and
source inspection after reload. Keeping these increments separate makes a search
miss distinguishable from a model ignoring evidence that search found.
Each behavior starts with a small failing contract test, followed by
implementation, verification and independent review.

Keep synthetic HTTP/browser fixtures in isolated database, queue and artifact
storage. The working application retains the single public PDF for manual review.
A temporary end-to-end script reuses its saved revision and idempotency keys;
it must not add another upload or issue fresh paid calls merely on every run.

Before tuning, have the owner review six cases: the full garage limit, a paraphrase
of its exclusions, the cross-page mudflow definition, an unsupported personal
premium question, an attempted change of document scope, and a question about
page 2. Freeze expected source passages and qualifications, not unstable chunk
IDs. This PDF cannot validate table retrieval; further documents and a held-out
set remain deferred. Deterministic model stubs verify software behavior; explicit,
budgeted live evaluation separately checks retrieval and answer quality.

Owner exercise: trace the garage answer back through its supplied passages to
page 5, then explain what remains durable if the worker stops after one batch.
The [indexing guide](indexing.md) provides a reading order through the actual
schema, chunk preparation, lifecycle and provider boundary.
