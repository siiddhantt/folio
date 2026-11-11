# Automatic summaries

Folio summarizes the complete available evidence from one extraction revision.
The owner selected one bounded model call per attempt, automatic generation and
saved-result reuse. Section-by-section synthesis, embeddings and retrieval are
deferred. This document describes the current contract; [status](status.md)
distinguishes checked software behavior from unresolved model-quality limits.

## What the reader gets

A short overview and normally 3–5 distinct key points, with source-page links.
On November 11 the owner accepted 1–2 points when a short document does not
support more. The system must not pad the summary to satisfy a minimum count.
Known extraction gaps remain visible. Summary failure never hides recovered
evidence or the original PDF.

The same prompt applies to reports, agreements, research and fiction. It chooses
important content from the document rather than imposing categories such as
risks, dates or recommendations. It uses no document-specific reference answers.

## From evidence to a saved result

1. The transaction publishing a usable extraction also inserts a unique summary
   intent for that revision. A disabled or invalid summary configuration records
   an unavailable reason without failing extraction.
2. The dispatcher sends work through the existing RQ queue. PostgreSQL owns its
   state, attempts and retry decisions. Duplicate delivery cannot claim a run
   already owned by a worker.
3. Preparation reads **all** stored source elements in reading order, including
   table structure, source IDs, physical pages and known coverage gaps. Detailed
   bounding boxes and offsets remain in storage; they do not consume model input.
   The paginated evidence API is not used to assemble model input.
4. The worker verifies the model route, tokenizer, context and prices. It counts
   the assembled messages and schema with a margin, then checks input, output
   and combined limits. Oversized inputs become unavailable; none is truncated.
5. Before the paid request, a transaction locks the shared budget account and
   reserves the permitted cost. It saves the input hash, source IDs, parser,
   preparation, prompt, schema, model profile and token configuration.
6. A complete response must satisfy the output schema and cite IDs from that
   revision. The current owner publishes the result and settles known usage.
   Reading or reloading the document only reads the saved state.

There is no Generate, Regenerate or Resume control. Old revisions without a
summary intent return `not_scheduled`; enabling summaries does not backfill them.
Runtime settings are captured when usable extraction is published. The effective
input hash and prompt/schema/preparation versions are recorded at first admission;
a never-admitted queued run can use newer code after a deployment. An admitted
retry must match that saved manifest rather than silently generating a different
summary. The manifest, not the earlier policy's version snapshot, describes the
actual generation input.

## What the prompt does, and what it cannot prove

The versioned prompt in [preparation.py](../src/folio/summaries/preparation.py)
asks for concise source-based coverage, important qualifications, negation,
conditions, numbers, units, attribution and uncertainty. It treats instructions
inside the uploaded document as content. It requires citations supporting each
whole claim and forbids invented facts, IDs and claims of reading missing pages.

The current prompt/schema/preparation versions are 5/3/3. The prompt requests
one central idea per point, a 60-word overview and 35-word points. These word
targets are guidance, not mechanically enforced limits. The schema permits at
most eight source references per statement; the model must narrow an overbroad
claim rather than omit support. Folio rejects an oversized reference list instead
of silently trimming it. Preparation retains non-null parent links, including
caption-to-table relationships, while omitting geometric metadata from model input.

| Responsibility | Check |
| --- | --- |
| Prompt | Choose salient content, paraphrase faithfully, preserve qualifications and ignore embedded instructions. |
| Output schema | Bound the shape, number and length of statements and citation lists. |
| Application | Reject incomplete responses and foreign citation IDs; enforce admission, ownership and spending; render stored gaps. |
| Source review | Check whether a cited passage actually supports the claim and whether important content was missed or distorted. |

Strict JSON is a formatting guarantee, not evidence of factual accuracy.
Likewise, a valid evidence ID can point to an irrelevant passage. Neither check
replaces source review. Prompt instructions also do not establish immunity to
document prompt injection.

## Recovery and spending

The allowance is $1 cumulatively for this deployment and $0.40 per
document, including retries and uncertain calls. The owner raised the original
$0.10 document limit on November 11 for a stronger-model comparison after
source review found quality failures. A database row preserves the
allowance across restarts. There are at most two attempts. Admission reserves
the verified route's full prompt ceiling plus the configured maximum output,
rather than treating a local token estimate as an exact billing bound.

A timeout can mean the provider finished and billed the request while Folio
never received the answer. Such an attempt retains its entire reservation. A
retry needs a fresh reservation. A stale response cannot publish over a newer
owner. This prevents duplicate publication; it does not promise exactly-once
provider billing. Unknown usage is reported as unknown, not zero.

The global budget row serializes short admission and settlement transactions.
It is a deliberate local-use limit, not an account/billing platform. Network
calls occur outside those transactions. The shared artifact volume and current
queue remain single-host infrastructure; multi-host storage and throughput
engineering are later work.

The indexes in migration 005 support three actual lookups: pending dispatch
ordered by time, expired worker leases, and summaries for a document. The first
two index only rows in the relevant state, so completed work is excluded. The
unique revision constraint prevents two summary records for one extraction. These
indexes do not establish a measured scaling limit; use query plans and realistic
row counts before adding indexes for hypothetical filter combinations.

## Read and inspect the implementation

Follow [evidence publication](../src/folio/ingestion/publication.py),
[preparation](../src/folio/summaries/preparation.py),
[worker coordination](../src/folio/summaries/processing.py),
[durable state and spending](../src/folio/summaries/lifecycle.py), then the
[read API](../src/folio/summaries/routes.py) and
[summary panel](../web/src/summaries/SummaryPanel.tsx).
Prompt changes belong in preparation; provider protocol and token admission live
under `ai/`; retry, ownership and reservation changes belong in the summary lifecycle.

Try one failure exercise on paper: the provider finishes, but the worker dies
before saving the response. Which database row proves that a request might have
been billed? Why must a retry reserve money again? The answer is the attempt's
committed invocation and reservation, not Redis or a console log. A short
transaction makes the local reservation durable before the network call; it
cannot atomically commit a remote provider's bill with PostgreSQL.

## Evaluation without document coupling

A reference check such as “this agreement allows cancellation with 30 days'
notice” belongs to that evaluation document, not the production prompt. Freeze
the generic prompt, then compare outputs with independently read sources from
more than one kind of document. Keep unseen examples before tuning. A small set
finds errors; it cannot justify a general accuracy percentage.

Review important content, citation support, numeric and qualifier accuracy,
false certainty, contradictions and embedded instructions separately. Record
the exact model/route, prompt/parser versions, latency, tokens and observed cost.
Controlled responses in software tests verify queue, persistence, UI and budget
contracts; they are not evidence of model quality. Agent-proposed expectations
remain proposals until a human reviews them.

Research inspected November 10–11, 2026:

- [OpenAI GPT-5 prompting guide](https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide): clear, consistent instructions matter, especially with minimal reasoning. Agent planning/preamble examples are not needed for a short summary.
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses): schemas constrain form but can still produce factual errors; incompatible inputs need a defined fallback.
- [Hamel Husain and Shreya Shankar's evaluation FAQ](https://hamel.dev/blog/posts/evals-faq), modified September 21, 2026: task-specific human review and separate development/held-out examples inform the evaluation method. These are practitioner recommendations, not a universal standard.

The earlier hierarchy comparison remains relevant only if the owner later
selects larger-input support. Splitting a document into section summaries can
reduce the input per call, but adds calls, recovery state and opportunities to
lose qualifications; it does not inherently reduce total tokens or spending.
