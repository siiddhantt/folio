# Document summaries

Status: automatic-only generation and output format accepted November 10, 2026. The remaining
design below is a proposal. Model/route, numerical limits and final
processing policy remain open; no paid evaluation is authorized yet.

## Outcome and order

Create a persisted summary with citations from one immutable extraction revision.
Users can continue reading extracted evidence while summary work runs. Extraction
and summary have separate outcomes; summary failure must not remove evidence.

Accepted output: one short overview and 3–5 key points, with citations on factual
claims and known extraction gaps visible alongside the result. Points reflect
the document's actual content; do not force every PDF into dates/risks/findings
sections. There is no separate invented insight taxonomy in this version.

The proposed development sequence is preparation, summary, then embedding-backed
retrieval. This is not a future runtime dependency: summary and embedding jobs
can independently consume prepared evidence; summary failure must not block search.
Preparation groups the stored evidence, preserves its source references and
counts the actual serialized input. It is local work and does not require
embeddings. Retrieval can later use smaller units from the same source model;
summary groups and retrieval chunks need not share a token size or tokenizer.
Do not reparse the PDF merely because a generation or embedding model changes.

## Input coverage and routing

Prepare text and tables with their headings, qualifiers and original source IDs.
Record included evidence and deliberate exclusions with reasons. Page/byte limits
do not imply token limits. Count instructions, source labels, table serialization
and any repeated context, as well as the document text. Reserve output capacity,
including reasoning where applicable, and a tokenizer uncertainty margin.

| Approach | Suitable use | Tradeoff |
| --- | --- | --- |
| One complete-input call | The entire prepared document fits cost/context bounds and an evaluated quality range | Fewest calls and shared cross-section context; large capacity alone does not prove reliable attention. |
| Section notes, then synthesis | The complete input exceeds a single-call bound | Bounded requests, resumable groups and limited parallelism; intermediate output costs more and compression can lose qualifications. |
| Sequential refinement | Each step must update the previous result using another section | Serial latency and repeated summary inputs; later updates can lose earlier facts. Not the recommended default. |

The earlier proposal was a size-aware complete-input path with hierarchical processing
for larger documents. A smaller complete-input-only increment was offered, with a
visible unavailable reason above its limit. The owner instead requested further
research into handling large documents before selecting the execution strategy.
Neither limiting summaries to one call nor a specific hierarchy is accepted yet.
The 150-page design example does not change ingestion's current 100-page cap.
Select thresholds after inspecting prepared inputs and comparing
actual outputs. Do not silently truncate to the beginning, select only similarity
search hits, or call a partial result a whole-document summary. If no plan fits the
total budget, report that boundary and keep the parsed document usable.

For hierarchical processing, notes retain source IDs, important figures,
qualifying conditions and uncertainty. Synthesis receives all successful scheduled
groups and preserves references to original evidence. Marking a summary complete
for its declared input requires every scheduled group to succeed. Failed groups
are recorded and retried within bounds; they cannot silently disappear. Whether
to display an explicit partial summary before recovery remains a product decision.

Processing every group proves input coverage only. It does not prove retention of
every important fact, correct interpretation, or citation support. The source may
itself be incomplete: retain known extraction gaps and avoid claiming visual
understanding of figures when only their text was recovered.

## Reuse, resource limits and failure boundaries

### Automatic generation only

Accepted: usable extraction starts summary work automatically, subject to the
agreed operating limits. There is no Generate, Regenerate or Resume control and
no manual generation endpoint in this version. Reading a saved document does
not trigger another generation. Automatic recovery belongs to the same workflow.

Proposed invariant: for the same revision and summary specification, reuse the
saved result or existing work, or atomically accept one new run. Repeated delivery
must not create competing runs. Keep parsed evidence readable while a summary
is pending, unavailable or failed.

Before accepting model work, reuse or prepare the source manifest, plan the
bounded calls and reserve the permitted budget. Concurrent callers cannot both
claim the same remaining allowance. A run that cannot be admitted stays visibly
unavailable for that reason; do not secretly truncate its input. At execution,
apply the same limits to subsequent groups, synthesis and retries.

Recommendation: application-wide and per-document settings initially. Accounts,
billing and subscription plans are deferred; a future plan can supply limits to
this admission decision without creating a separate summary engine. Changing a
model/prompt configuration should not silently regenerate old documents merely
because somebody opens them.

- Persist summaries and intermediate notes with the extraction revision and
  preparation, prompt, schema, model/route and generation-setting versions.
  Matching completed work is served from PostgreSQL without another model call.
- Deduplicate concurrent requests in the database. Resume unfinished groups after
  interruption; changing a prompt or model deliberately creates another version.
- A provider call and a database commit are separate operations. A timeout or
  crash after generation may leave an uncertain billed outcome. Budget retries;
  do not promise exactly-once billing.
- Bound total input/output tokens, planned calls, reduction depth, concurrency,
  elapsed time and spend per run, including retries. Reserve spend for concurrent
  in-flight calls rather than checking each against the same unused balance.
- Record measured stage durations and provider-reported input/output/reasoning/
  cache usage and cost. Unknown usage stays unknown. Compare time until readable
  evidence with time until the summary is ready.

The owner selected automatic-only generation to keep the product's controls and
workflow small. This selects the trigger, not a model or spending allowance.
Provider prompt/response caching is
optional additional optimization, not Folio's durable reuse mechanism. OpenRouter
documents that simultaneous identical response-cache misses both run and are
billed, so provider caching does not replace the in-flight guard.

## Cost illustration, not a measurement

OpenRouter's public Luna catalog was checked November 9: short-context standard
input is $0.10 and output $0.50 per million tokens. Luna remains an evaluation
candidate, not a quality-approved selection.

Assume 48,000 document tokens and an 800-token final summary:

| Path | Input tokens | Output tokens | Base model cost |
| --- | ---: | ---: | ---: |
| Complete input, one call | 48,000 | 800 | $0.00520 |
| Six 8,000-token groups, each producing 400-token notes, then synthesis | 50,400 | 3,200 | $0.00664 |

These calculations exclude instructions, citation labels, overlap, reasoning,
validation calls, retries, cache writes/discounts, route/tier differences and
credit-purchase fees/taxes. They are not upper bounds or measured Folio costs.
Hierarchy lowers input size per call; it does not inherently lower total tokens.
With group concurrency two, six groups need roughly three waves followed by
synthesis. Actual seconds require measurement on the selected route.

## Review before implementation

With the automatic trigger and format accepted, agree input/coverage policy, versioned
persistence and retry behavior, and model/route plus spending limits. Validate
token/source preparation before connecting generation. Use known evidence near
the beginning, middle and end, a cross-page qualification and a table to review
summary quality. Test stored-result reuse, duplicate requests and recovery with
deterministic model substitutes; measure real model quality separately under an
explicit evaluation budget. A maintained synthesizer can provide useful
orchestration, but its default trimming, source mapping and retry behavior must
be checked against this contract before adoption.

## Primary references

- [LlamaIndex response synthesis modes](https://developers.llamaindex.ai/python/framework/module_guides/querying/response_synthesizers/)
- [Docling chunking](https://docling-project.github.io/docling/concepts/chunking/)
- [OpenRouter Luna pricing](https://openrouter.ai/openai/gpt-6-luna)
- [OpenAI Luna specifications](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [OpenRouter prompt caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching)
- [OpenRouter response caching](https://openrouter.ai/docs/guides/features/response-caching)
