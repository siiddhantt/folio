# Document-to-conversation evaluation

Latest: [November 15 caption and partial-answer fix verification](#november-15-caption-and-partial-answer-fix-verification).
The earlier run below remains unchanged as historical evidence.

November 13, 2026; application baseline `1c793a9`. One fresh frontend upload,
one conversation, twelve sequential UI-submitted questions and one actual
background history compression. No answer was replaced by a tuned retry.
This is a development evaluation, not a general accuracy or load benchmark.

## Source and method

The US Department of Energy's July 2022
[Energy Saver guide](https://www.energy.gov/sites/default/files/2022-08/energy-saver-guide-2022.pdf)
has 56 physical pages, numeric recommendations, tables and captions.
SHA-256: `416398e39c65d91687a287c6f82a8f63723a5f4e5027702f5d144ccbf1d1f504`.
Physical page numbers are four higher than the printed labels from physical p5.
The PDF includes third-party images and is not redistributed in this repository.

A source-review agent prepared questions and expected passages before seeing
Folio's outputs. A separate reviewer checked saved retrieval, citations, notes
and original-page renders. These agent-proposed expectations are not a
human-approved gold set. The hypothetical house facts were invented for testing.
No current installer prices, rebates or home-specific advice were verified.

Frontend actions used the real file picker and composer. Read-only API/database
inspection captured every turn's frozen context, selected evidence, attempts and
usage. Worker logs explained parser fallback messages and stage completion.
Raw traces, source files and screenshots remain outside tracked source.

| Component | Frozen configuration |
| --- | --- |
| Parser | Docling 2.148.0, normalization 1, English OCR |
| Index | HybridChunker peer merging/heading preservation, 512-token target; 1,536-dimensional `text-embedding-3-small` via OpenRouter/OpenAI |
| Summary | DeepSeek V4.1 Flash 1017 via OpenRouter/Together; prompt/schema/preparation 6/4/3; 64,000 input, 16,384 output tokens, reasoning off |
| Answer | Direct `gpt-5.2-2025-12-11`; profile `openai-gpt-5.2-2026-11-13`; prompt/schema 3/3, resolver 2, retrieval 2; 16,384 input/4,096 output, reasoning off |
| History | Temporary trigger/target/ceiling 2,000/1,000/3,000 tokens; latest two exchanges unchanged. Normal 6,000/3,000/8,000 restored afterward. |

## Processing and summary

Extraction published 921 elements after about 91.77 seconds of measured parser
work. Summary acceptance-to-ready time was 17.85 seconds, including queue wait
(4.40 seconds from worker start); indexing took 42.17 seconds from
start to finish across four embedding batches, publishing all 120 chunks.
There were no worker retries or terminal execution failures in this run.

Physical pages 2 and 4 had no recovered content and were visually confirmed blank.
Coverage retained both warnings, duplicated in diagnostics but not the distinct
page list. Parser logs included OCR orientation warnings and a dense-vector
separator fallback; publication succeeded. This does not prove full extraction
accuracy elsewhere. Two chunker warnings also remain recorded.

The saved summary used 41,631 input and 396 output tokens and stopped normally.
No major factual contradiction was found in the inspected overview/five points,
but two citation sets were incomplete: the overview's topic list and the
south-facing-window detail. A water-heating point also blurred energy usage
versus expense. Resolving citation IDs therefore did not establish full support.

## Conversation results

The scenario established a $1,200 budget, $1,800 annual heating/cooling bill,
climate zone 5 and R-19 attic insulation. The user then corrected a tentative gas
furnace to an electric air-source heat pump.

| Turn | Question/check | Observed result |
| --- | --- | --- |
| 1 | Where to start before equipment purchases | Supported whole-house planning/air-sealing advice; no invented quote or diagnosis. |
| 2 | Thermostat change and 10% of the bill | Correct 7–10°F/eight-hour guidance and $180 calculation, with potential-saving and heat-pump qualifications. |
| 3 | Correct furnace to heat pump | Correct interpretation and source-supported control/backup-resistance caveat. |
| 4 | Zone-5 table and code/thickness qualifications | Correct total R60/R49/R30 values. Needed code-footnote and R-value-definition chunks ranked 9 and 11, outside six supplied passages; qualification answers were incomplete. |
| 5 | Air-sealing savings and assumed payback | Needed 10–20% passage ranked 8. Honest abstention, but failed the requested calculation: $180–$360/year and roughly 3.3–6.7 years for assumed $1,200 cost. |
| 6 | House leaks versus ducts | Supported comparison and professional testing requirement. |
| 7 | Ambiguous “Could I do that myself?” | Asked which work was meant; only the resolver ran. |
| 8 | Clarify ducts and recall corrected system upkeep | Remembered heat pump; answered duct testing. Maintenance chunk ranked 7, so that half was unanswered. |
| 9 | Does 50% mean halving this bill? | Correctly retained comparison against electric furnaces/baseboards and heating-electricity scope; rejected automatic bill halving. |
| 10 | Fan setting, direction and empty room | Supported about +4°F, counterclockwise and off when unoccupied, including caption evidence. |
| 11 | Local installer and exact utility rebate | Asked for work/location/utility without explaining the historical-PDF boundary. No fabricated amount, but incomplete handling of unavailable personalized information. |
| 12 | Recall early facts and give a plan after compression | All five facts retained. Incorrect PDF citation on those user facts; general plan supported but omitted heat-pump-specific guidance (tips ranked 17). |

The missed passages were extracted, indexed and vectorized. All six selected
chunks fit their requests; evidence trimming did not cause these misses.
This isolates a retrieval-ranking problem. It does not prove that simply raising
the result count or adding another model will solve it on other documents.

The mixed-source failure in turn 12 also has a contract issue: the current answer
schema requires PDF source IDs for every statement in a document answer, while
its first statement recalls user history. A separate transcript-only resolver
path does not provide valid attribution for that mixed response.

## What happened to history

History before turns 1–11 grew from 9 to 2,054 tokens. After turn 10, background
work compressed turns 1–8 from 1,590 to 859 tokens, retaining the two newest
exchanges. It ran for about 12 seconds. Turn 11 had already captured raw history
and did not wait; turn 12 used the ready notes plus original turns 9–11.

Turn 12's history was 1,454 tokens instead of 2,185 without compression: 731 fewer
tokens, about one-third less. The notes preserved the five facts, correction,
weekday schedule and unresolved questions. One note incorrectly attributed the
duct clarification to turn 7 rather than turn 8. The target is guidance, not a
strict output length: notes exceeded their 527-token requested target while
still reducing the prefix and staying within execution limits.

This demonstrates one background compression with early test thresholds.
Repeated compression, the hard-limit waiting path and normal thresholds were
not exercised live. The complete transcript remained stored and reloadable.
History size excludes instructions, question, evidence and schema. Actual answer
inputs ranged from 2,813 to 4,490 tokens, outputs from 73 to 327; all stopped
normally. A smaller history does not guarantee a smaller request when the new
question retrieves different passages.

## Latency, spending and interface

Acceptance-to-terminal time across twelve turns was 3.09–10.32 seconds, median
8.86. Two clarification turns skipped retrieval/answer generation. Median stage
times were 2.97 seconds for rewriting, 1.22 for query embeddings and 3.83 for
answers. These timings describe one sequential run, not concurrent capacity.

| Paid work | Calls | Accounted USD |
| --- | ---: | ---: |
| Document summary | 1 | 0.01296450 reported |
| Document embeddings | 4 | 0.00043422 reported |
| Query embeddings | 10 | 0.00001572 reported |
| Answers | 10 | 0.08686650 estimated |
| Follow-up interpretation | 11 | 0.03741605 estimated |
| History notes | 1 | 0.01418725 estimated |
| Total | 37 | 0.15188424 |

Direct OpenAI usage-based estimates total $0.13846980; provider-reported charges
total $0.01341444. No unknown billing or outstanding holds remained. The run
stayed within its unchanged allowance; prior consumption was carried across the
authorized reset. Compression added a paid call, so this run does not establish
a net cost saving.

The browser showed loading/completion states, followed arriving answers at the
bottom and preserved twelve questions/responses on reload. Scrolling back stayed
put. Source drawer and original-page navigation worked. Older preview snippets
remained in DOM with unchanged text/dimensions; their absence in an offscreen
accessibility snapshot was not lost data. The Latest reply action was absent in
the final idle inspection and was not exercised there. Screenshot capture timed
out, so this pass does not claim screenshot-based visual verification.

## Next checks

Prioritize correct attribution for mixed history/PDF responses, then compare
retrieval coverage on new questions. Improve memory-note references and summary
citation support with focused regressions/evaluations. Do not tune only against
this guide and call the resulting examples a held-out result.

Earlier parser, chunking and model comparisons remain available in the
[historical docs](https://github.com/siiddhantt/folio/tree/1c793a9891e4aaf833acce53987eb7ee1beee3e0/docs)
and [parser comparison](https://github.com/siiddhantt/folio/tree/1c793a9891e4aaf833acce53987eb7ee1beee3e0/experiments/ingestion).
Those records include failed examples; this run does not erase them.

## November 15 four-arm comparison on two new PDFs

This is the pre-fix comparison. The subsequent regression run is recorded below.

The owner accepted a comparison of grouping and Jev together, each separately,
and the current vector-six baseline before selecting a default. The same single
runner used two fresh official PDFs:

- NASA's four-page [Orion fact sheet](https://www.nasa.gov/wp-content/uploads/2023/03/orion-factsheet.pdf),
  SHA-256 `2206b1140c1d20bd28d2ebcf098f2f203471f5c62b72abb5e88493bd6004ec6a`.
  Questions concern this historical document, not current mission status.
- EPA's nine-page [SepticSmart homeowner guide](https://www.epa.gov/sites/default/files/2015-06/documents/septicsmart_longhomeownerguide_english508_0.pdf),
  SHA-256 `b7657f278271a4218592c9bbf2de2081a1aeed0fdaf79b73265378a07874e21c`.

Separate agents inspected the original pages and froze five questions per PDF
before seeing rankings: four positive questions and one plausible unanswerable
control. The positives contain 18 required facts across entity lookups, units,
conditions, complete lists and paired locations. These are source-checked agent
labels, not human gold. No question or method was tuned after results appeared.

The unchanged grouping rule packs adjacent whole chunks on the same physical
page within 512 tokens, preserving every original chunk and source link. NASA's
nine chunks became four; EPA's 34 became 11. Jev `jev-1.14.0` independently scored
every candidate with the frozen four-level rubric, using three alternating
requests per query and arm. Repeat zero supplied answer evidence. Both vector
arms shared one measured query-embedding call. Grouped embeddings were generated
once per document. Each question/arm received one GPT-5.2 answer with the same
production first-turn prompt, empty history and 1,024-token output limit.

| Method | Required facts retrieved | Complete positive answers | Outputs accepted by v3 validator | Median retrieval components | Median GPT input tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original vector-six | 17/18 | 7/8 | 8/10 | 0.757 s | 1,045 |
| Grouping + vector-six | 17/18 | 7/8 | 9/10 | 0.751 s | 1,483 |
| Jev on all original chunks | 17/18 | 7/8 | 8/10 | 0.378 s | 1,084 |
| Grouping + Jev | 17/18 | 7/8 | 8/10 | 0.357 s | 1,542 |

For EPA, every method retrieved 10/10 facts and produced four complete, supported
positive answers. For NASA, every method retrieved 7/8 facts and produced three
complete positive answers. The missing fact was visibly present in a photo
caption and in extraction, but the chunk plan excluded it as `outside_body`.
It remained in the evaluation denominator. Neither grouping nor reranking can
recover a passage absent from their candidate set.

Independent reviews inspected all 40 answers and actual cited passages. All 28
complete positive answers had supported claims and citations. NASA's four
location replies gave the supported part and acknowledged the missing part,
but selected `insufficient_evidence` while retaining a citation. EPA's negative
control did the same in three arms. Folio's v3 validator rejected citations on that outcome, so
these seven responses were unusable under that contract despite grounded
raw text. All eight negative-control texts avoided inventing the absent fact;
five passed validation. EPA responses also phrased absence at document scope
rather than limiting it to supplied passages, and the passing grouped response
included an awkward literal outcome prefix. One successful negative sample does
not establish that grouping fixes output compliance.

Jev placed complete evidence first for all seven questions whose full answers
survived indexing, versus five for either vector arm. All three Jev repeats
preserved the measured fact coverage. The exact selected ordering agreed across
repeats for only 3/10 original-chunk queries and 5/10 grouped queries; this is not
a claim of deterministic scoring. Grouping did not add quality on these sources:
EPA facts were already co-located, and NASA's four groups supply the entire
searchable text. Six groups also mean more text than six original chunks.

Retrieval timing includes each vector query's embedding call plus local cosine,
or the Jev HTTP/decode/validation call. Jev needs no query embedding when all
passages are scored. Its table values are medians of the ten per-query medians;
each per-query median has three samples. All 30 original-chunk samples ranged
from 0.306 to 0.575 seconds, while grouped samples ranged from 0.299 to 1.127.
A persistent HTTP client followed a separately recorded synthetic probe. These
are prototype components, excluding database, queue and UI time. They do not
establish production latency percentiles or throughput.

Median generation times were 1.94, 2.13, 2.14 and 2.03 seconds in table order.
Median sums of retrieval, prompt preparation and generation were 2.77, 2.91,
2.60 and 2.39 seconds. Generation was sampled once per question/arm; latency
variation and differing prompt volumes prevent attributing every difference
to the retrieval method. Grouped embedding preparation took 1.20 seconds for
NASA and 2.50 for EPA, once at index preparation rather than per question.

At TypeSafe's [published rate](https://docs.typesafe.ai/models), median ranking
costs were $0.000264 on original chunks and $0.000155 on grouped chunks. These are
token-priced estimates, not invoices. The 114 paid calls, including 40 answers,
60 ranking samples, probes and embeddings, cost $0.153356644. Normal ingestion's
summaries and original embeddings added $0.03026877, for $0.183625414 total new
spending. Both $0.18 experiment envelopes closed with no uncertain holds; the
shared remaining allowance was $0.282480974. Existing usage was not reset.

All 114 responses replayed from cache with byte-identical ledgers and unchanged
answers/rankings. Original live results and timing are retained separately from
the replay outputs. The new grouped-ranking check failed before implementation,
then passed; existing response, provenance, replay and isolated PostgreSQL budget
checks also passed. Independent code review checked the four-arm runner and
fresh-document admission guard. Sources, labels, snapshots, full paid payloads,
reviews and exact runner source remain under ignored evaluation directories.

This trial supports Jev's practicality for these small candidate sets, and finds
no extra answer-correctness gain from combining it with grouping on these two
PDFs. It does not invalidate the earlier report's grouping/Jev improvements.
The caption exclusion and partial-answer/output-contract failures led to the
subsequent focused fixes below. Production remains vector-six; no default was selected.

## November 15 caption and partial-answer fix verification

The owner accepted two focused fixes before choosing a retrieval default. Index
preparation 3 traverses body text nested inside pictures in both serialization
and source mapping. The missing NASA caption was a nested body-text element,
not a page footer or an attached-caption reference. Furniture remains excluded,
attached captions are not duplicated, and physical-page/source links survive.
Existing indexes keep their captured preparation policy; version 2 is still
reproducible. Newly prepared NASA chunks grew from 9 to 11 and grouped passages
from 4 to 5. EPA retained 34 chunks, with 12 groups instead of 11. Two EPA chunks
gained picture text, including some OCR noise, without changing the required
answer-bearing passages. This does not establish complete extraction fidelity.

New answer prompt/schema 4 allows partial answers and insufficient-evidence
responses to cite supported details while explaining the missing information.
Pure questions and limitations need no source citation. Every supplied source
ID must still belong to the retrieved evidence; normal factual answers still
require citations. Malformed or truncated model output is still rejected. Old
accepted turns retain their original prompt and validator policy. Reconstructing
all 40 earlier prompts under version 3 produced identical bytes. Applying only
the new validator to the saved responses reduced seven rejections to zero,
without paid calls. A real-database regression also verifies that a cited partial
answer is saved and reloads successfully after the previously observed failure.

Fresh uploads of the identical NASA and EPA PDF bytes exercised normal workers,
summaries and indexing. Independent remapping retained every frozen question and
expected source fact. All 165 NASA and 155 EPA normalized elements matched the
earlier extraction, including IDs, text and locations. Thus the recovered caption
was an indexing change, not a lucky parser rerun. Model, gateway, reasoning
setting, 1,024-token answer cap, grouping rule and Jev rubric were unchanged;
index preparation and answer prompt/schema were the intended differences.

| Method | Required facts retrieved | Complete positive answers | Valid outputs | Median retrieval components | Median generation | Median GPT input tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original vector-six | 18/18 | 8/8 | 10/10 | 0.748 s | 2.272 s | 1,061 |
| Grouping + vector-six | 18/18 | 8/8 | 10/10 | 0.743 s | 2.247 s | 1,834 |
| Jev on all original chunks | 18/18 | 8/8 | 10/10 | 0.405 s | 2.297 s | 1,418 |
| Grouping + Jev | 18/18 | 8/8 | 10/10 | 0.362 s | 2.317 s | 1,817 |

Independent reviews inspected the actual generated claims and cited passages in
all 40 responses. Every positive answer was complete and supported; all eight
negative responses abstained without inventing the absent fact. The formerly
missing NASA propulsion-testing caption was retrieved and actually cited by all
four methods. All 60 repeated Jev selections preserved required-fact coverage.
EPA negative wording still sometimes claims document-wide absence rather than
absence from the supplied passages; full-source review confirms absence here,
but that wording remains a generalization risk. This regression set has already
informed the fixes, so it is not a fresh held-out benchmark or human gold.

Timing definitions match the previous run: query embedding plus cosine for vector
arms, and HTTP/decode/validation for Jev, with persistent connections after a
probe. Three samples per query/arm measure Jev; generation has one sample per
question/arm. These exclude application queue, database and UI time. All methods
tie on answer quality here, and grouping supplies NASA's entire five-passage
index. There is no evidence from this small rerun to select a new default.

The 114 paid responses cost $0.173453764: $0.159604600 in direct OpenAI estimates
and $0.013849164 in TypeSafe estimates. Fresh ingestion added $0.029664770,
totalling $0.203118534. Both $0.15 experiment envelopes closed within their limits.
All 114 responses replayed with byte-identical ledgers, answers and rankings;
original live timings and source hashes are preserved separately. Sixty-four
targeted software checks passed, including real database persistence and Docling
worker checks; lint and independent code/source reviews also passed.

A separate live browser rehearsal used the newly indexed EPA guide and the
unchanged vector-six default. Three questions covered tank-pumping measurements,
a contextual follow-up asking for all four pumping-frequency factors, and an
unavailable exact tree-planting distance. Answers cited the expected physical
pages 3, 4 and 7 respectively; the last response preserved its supported citation
while reporting insufficient evidence. Opening the original page and reloading
the complete conversation worked. These calls used direct OpenAI and cost
$0.012321380, bringing this increment to $0.215439914. The remaining shared
allowance is $0.067041060 with no holds. No allowance was reset or increased.

New work uses direct OpenAI; old indexes retain their frozen embedding route,
including OpenRouter. Grouping and Jev remain experiments. Ignored artifacts
under `.local/retrieval-evaluation/after-fixes/` retain sources, source labels,
captured policies, live/replay results, ledgers and independent reviews. The
browser receipt and screenshots remain outside tracked source as well.

## November 15 controlled retrieval comparison

The owner accepted separate chunk-grouping and all-chunk reranking experiments,
plus correct-evidence generation, before changing the default. The single
[`evaluate_retrieval.py`](../scripts/evaluate_retrieval.py) runner preserves the
live index and conversations. Private source material, labels, exact answers and
receipts remain in ignored local artifacts.

An independent agent froze seven questions against extracted evidence and
rendered original pages before results: three development questions, three
held-out positive lookups and one unanswerable control. Six answerable questions
require seven facts. Labels combine source-ID alternatives with text/value
anchors because a table ID can appear in chunks that omit the required row.
These are agent-curated labels from one document; no human-gold or cross-document
generalization claim follows.

The baseline uses the original 45 chunks. The grouping candidate joins adjacent
whole chunks on the same physical page within the existing 512-token limit,
yielding 27 groups while preserving every original text and source link. It adds
no generated semantic labels and excludes no content. Original vectors are
reused; new vectors use the same 1,536-dimensional text-embedding-3-small model
through direct OpenAI. The original primary query vector is reused; six new
question vectors are embedded once and shared by both vector arms.

The separate reranker is
[`cross-encoder/ms-marco-MiniLM-L6-v2`](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2/tree/233902d25c440f23af6f7d6e94d2946bac0bee0a),
revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`, Apache-2.0. It scores all 45
original chunks. Query-preserving 512-token windows with stride 64 produce 48
pairs per question; maximum window score ranks each complete original chunk.
Six passages then reach the answer model. No model dependency or production
selector was added.

| Method | Required facts within six | Fully covered questions | Held-out positive questions |
| --- | --- | --- | --- |
| Original vectors | 5/7 | 4/6 | 3/3 |
| Same-page groups, vectors | 7/7 | 6/6 | 3/3 |
| MiniLM reranking of all originals | 5/7 | 4/6 | 3/3 |

The original failing question's first answer-bearing evidence moved from rank
eight to rank one with grouping. MiniLM moved it to rank thirty and continued
to favor generic repeated headings. This is evidence for the grouping candidate
on these cases; it does not establish that reranking generally fails.

Four fresh answers compared original-six, grouped-six, reranked-six and one
known-correct original passage for the same question. The original prompt hash
was reproduced before swapping evidence. All arms used GPT-5.2 snapshot
`gpt-5.2-2025-12-11`, reasoning none, the same prompt/schema/history arguments,
and a common experimental 1,024 output-token cap instead of the live 4,096 cap.
All outputs finished normally, using 51–98 output tokens across the five calls.
Grouped and correct-source answers were correct with supported citations;
original and reranked evidence produced grounded insufficient-evidence outcomes.
Successful answers also supplied unnecessary but supported contact details.
The reranked unanswerable control correctly abstained; its mostly generic
retrieval makes it a weak hallucination challenge. Other positive questions
were retrieval-only, so their generated-answer quality is unmeasured.

Three repeated warmed reranks per question had medians of 11.01–13.60 seconds
on four native ARM Docker CPU threads, batch eight. Initial model download/load
took 25.24 seconds separately. Global 512-token padding wastes work on short
passages, and no GPU/Metal path was used. These are measurements of an
unoptimized experiment, not intrinsic reranking latency or a service percentile.
The five generation calls took 1.67–2.38 seconds. Grouping increased the primary
answer's actual prompt from 1,005 to 2,557 tokens; the one-passage oracle used
517. Retaining six larger groups is not a free input-cost improvement.

Seven paid calls cost $0.01502742 in token-priced estimates, within the $0.12
envelope. The separate ignored ledger carries costs forward through the shared
allowance; ordinary application-turn metrics do not contain these experiment
calls. All charges settled, and all seven responses replayed from cache without
network calls or ledger changes. Source/packing checks passed after an observed
initial failure. A failing uncertain-usage replay check led to a fail-closed
fix. Session-local PostgreSQL account tests verified reservation/refund behavior
without touching the live account. Independent code and source-support reviews
found no blocking issue. Production remains vector-six; broader sources and
answer minimality need evaluation before adopting the candidate.

### Jev follow-up

The owner requested a Jev trial. The same runner reused the frozen labels,
45 original chunks and saved baseline results. The documented version
`jev-1.14.0` passed a synthetic contract probe and was reported in every scoring
response. One HTTP request per query carried 45 independent Score questions:
shared state contained only the query, and each question contained only its own
candidate passage. The common four-level rubric distinguishes unrelated text,
topic overlap, partial evidence and complete direct evidence. Code sorts the
score, not confidence. The request shape follows TypeSafe's
[structured-question](https://docs.typesafe.ai/primitives/advanced) and
[Score](https://docs.typesafe.ai/primitives/score) contracts; its
[reranking cookbook](https://docs.typesafe.ai/cookbooks/rerank_typesafe) provides
related upstream evidence, not Folio measurements.

Jev supplied all seven required facts across the six positive questions. The
first passage fully supported each question in all six cases, including the
three previously held-out lookups. Independent review checked actual text and
table-row associations, not just source IDs. The original identity question
then produced a correct GPT-5.2 answer with supported citations. The negative
control abstained despite receiving demographic evidence. The positive answer
still included unnecessary supported contact/address details, and duplicate
passages remained in the selected six.

The seven 45-passage requests took 0.476–0.605 seconds, median 0.495, measured
around HTTP, decoding and response validation. There was one sample per query,
with a reused connection after the synthetic probe; no stability or service
percentile claim follows. GPT-5.2 took 3.51 seconds for the positive answer and
2.09 for the control, separately. Comparing this hosted service with the earlier
unoptimized CPU MiniLM runner establishes the observed alternatives here, not
an intrinsic model-speed ratio.

TypeSafe's [published rate](https://docs.typesafe.ai/models) is $0.042 per million
input tokens, with output free. Each full ranking request used about 19,000 input
tokens and cost about $0.0008 by that rate. The probe, seven rankings and two
GPT-5.2 answers totalled $0.012529818 in estimates, within the $0.08 envelope.
All ten paid responses replayed without network calls or changed receipts.
Both comparison runs together cost $0.027557238. Charges carry forward globally;
linked experiment admission now includes prior document evaluation charges and
respects lower current configuration caps. Normal application per-document
metrics still exclude external experiment charges.

Six controlled Jev contract tests covered candidate isolation, response order,
duplicate IDs, malformed-answer billing, invalid score distributions and usage
overruns. Runner checks additionally exercised the HTTP failure/billing boundary
and session-local PostgreSQL admission/refund behavior. Independent code and
answer reviews passed. The credential remains in ignored `.env`; the template
is blank. Original results and the exact earlier runner source are preserved.
No production provider or retrieval default changed. Jev and same-page grouping
both merit broader-source comparison; this run does not select between them or
measure their combination.

## November 14 retrieval comparison

One new 39-page EPA [Home Buyer's and Seller's Guide to Radon](https://www.epa.gov/sites/default/files/2015-05/documents/hmbuygud.pdf),
March 2024 revised edition. SHA-256:
`b3bca87cdb71d5c4bf38e578ccc4fde0898559b581cef976b428b1b0d852eddd`.
The owner accepted ten source-checked questions before execution, seven for
development and three held out. One independent agent mapped all 24 required
facts to complete supporting chunk groups without seeing ranks or answers;
another reviewed generated answers and citations. These are agent labels,
not human-annotated gold data or a general accuracy benchmark.

The official PDF's overlapping image table on physical p22 was excluded during
question selection. Physical p19's two-test table is intact but Docling flattened
its columns into separate chunks. All required facts survived in the index;
this does not establish full extraction fidelity. Figure text and furniture
exclusions, OCR noise and five chunker warnings remain inspectable.

### Execution and repeatability

A host engine interruption was recovered through a new extraction attempt.
The first index then failed safely before embedding: a picture-attached footnote
lacked its heading mapping. An offline check also found that structured contents
tables labelled `document_index` had been omitted from normalized evidence.
Focused failing regressions led to chunk preparation 2 and normalization 2.
Old requests keep normalization 1. The failed run was retained; a separate
upload exercised the fixes rather than rewriting its history.

The new run extracted 788 elements in 164.17 measured parser seconds and saved
78 chunks, maximum 511 tokens, in three embedding batches of 32/32/14. Indexing
took 42.08 seconds from worker start to finish. Summary worker time was 4.07
seconds. The summary's six claims were supported by their cited elements, but
its repeated risk/threshold coverage left practical steps underrepresented.

The [notebook](../notebooks/folio_demo.ipynb) completed all 14 code cells using
real HTTP, workers and models. A complete rerun made no POST requests and left
document/job totals and the spending ledger unchanged. Saved checkpoints expose
source elements, chunks, attempts, citations, usage and filtered worker logs.
Additional questions used the same conversation through the same HTTP routes.

Parser/model versions match the earlier run except normalization/preparation
above. Normal history thresholds remained 6,000/3,000/8,000; history grew from
9 to 1,617 tokens and did not require compression. No compression quality claim
follows from this run.

### Retrieval result

Every arm used the same saved question vector, resolved question, history,
source index, model profile and prompt preparation. Both reconstructed saved
inputs and recomputed vector-six inputs matched the original prompt hashes for
all ten turns. Hybrid combined vector12 and English keyword12 using equal
reciprocal-rank fusion with constant 60, returning six. Methods were fixed
before results; there was no tuning against the held-out cases.

| Method | Required facts supplied | Questions with complete evidence | Warm selection median | Mean prepared input | Estimated uncached input USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vector 6 | 19/24 | 7/9 | 0.85 ms | 2,812 tokens | 0.00492 |
| Vector 12 | 21/24 | 8/9 | 0.92 ms | 4,089 tokens | 0.00716 |
| Hybrid 6 | 17/24 | 5/9 | 17.39 ms | 3,453 tokens | 0.00604 |

Coverage excludes the unanswerable personal-values question. Development fact
counts were 15/19, 16/19 and 12/19; held-out positive counts were 4/5, 5/5 and
5/5 respectively. No selected chunk was dropped for input size, so selected and
supplied coverage are equal. The personal-values case is assessed separately.

Timings are medians of per-question medians from eleven warm repetitions, with
rotated method order, on one small local index. They exclude embeddings, prompt
preparation and generation; keyword search scans these 78 rows and is not a
scaling benchmark. Cost estimates average all ten prepared answer requests,
exclude the safety margin, use the frozen $1.75/million uncached input rate and
exclude output, rewrite, embeddings and caching. They are not actual invoices
or measurements of alternative model latency. No alternative answers were generated.

Vector12 recovered the p23 qualification that a two-test average of 4.1 pCi/L
still has about a 50% chance of a year-round average somewhat below 4. Hybrid
also found it, but displaced no-power detector evidence, long-term testing
details and post-mitigation confirmation testing on other questions. None supplied the
complete two-test table: setup chunks 40/41 and threshold chunk 43 were missing.
Wider retrieval recovered only that question's interference precaution.

### Delivered answers and remaining defects

| Case | Subject | Baseline result |
| --- | --- | --- |
| D01 | Detector power and more-than-90-day use | Complete, supported |
| D02 | Gravel and crawlspace exception | Complete, supported |
| D03 | Basement renovation testing | Complete, supported |
| D04 | Simultaneous/sequential passive tests | Failed output validation; required table evidence also absent |
| D05 | Year-round test duration and 48-hour minimum | Supported decisions; omitted daily/seasonal explanation despite supplied evidence |
| D06 | Sealing, mitigation and confirmation | Supported; omitted explicit home-design dependency despite supplied evidence |
| D07 | Well-water treatments and qualifications | Complete, supported |
| H08 | 4.1 average uncertainty and below-4 risk | Supported claims; missing the expected roughly-50% qualification, not retrieved |
| H09 | Three-day test, windows and weather | Complete, supported |
| H10 | Exact personal home reading and contractor quote | Failed output validation; rewrite also drifted toward generic cost-range guidance |

Eight delivered answers contained 20 supported statements; five covered all
frozen expectations. Both failed turns reached the validator branch rejecting
citations on a non-answer outcome. Their rejected text was not retained, so
neither successful abstention nor a particular hallucination can be inferred.
There were no replacement answers or hidden retries. These contract failures
are separate from retrieval coverage and must be addressed before calling the
workflow reliable for unavailable information.

Acceptance-to-terminal median was 8.13 seconds, including failures. Actual
answer input usage ranged from 1,418 to 3,552 tokens. Total accounted run cost
was $0.10113222 across 33 stage calls, including $0.02097327 for the two failed
turns: $0.08974770 direct-generation estimates and $0.01138452 provider-reported
summary/embedding costs. The earlier failed-index run's summary cost another
$0.0099258. Remaining shared allowance was $0.406827606, with no holds.

The recommended next comparison is generated answers with vector12: roughly
$0.00223 more estimated input cost per request here, with better measured
coverage. Fix the non-answer citation contract and preserve personal-question
intent in a separate focused increment. Do not adopt this hybrid rule or claim
vector12 fixes the table miss. Production remains vector6 pending an explicit
default decision. Existing mixed history/PDF attribution limits also remain.

Ignored local artifacts under `output/retrieval-comparison/` preserve frozen
questions, independent labels, exact vectors/context/profile snapshots, source
hashes, per-arm passages/timings, coverage scores and the answer review. The
connected notebook run is under `output/demo/folio/`; the earlier failure remains
under `output/demo/epa-radon/`. Source PDFs and raw traces are not tracked.
