# Document-to-conversation evaluation

Latest: [November 14 retrieval comparison](#november-14-retrieval-comparison).
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
