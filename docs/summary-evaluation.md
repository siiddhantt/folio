# Summary evaluation, November 11, 2026

These are small development observations, not a general accuracy benchmark.
Independent agent source review found the failures below; the owner has not yet
approved a human-labeled evaluation set. The prompt contains no reference facts
from the evaluation documents.

## Inputs and versions

- `tests/fixtures/mixed.pdf`: Folio's original synthetic three-page input, with
  native budget text, an English scanned renewal notice and a blank page. The
  parser reports no recovered content on page 3 with unknown cause; the model
  must not infer that this means the original page is blank.
- [NIST SP 800-207, Zero Trust Architecture](https://nvlpubs.nist.gov/nistpubs/specialpublications/NIST.SP.800-207.pdf),
  August 2020: 59 physical pages, 966,908 bytes. SHA-256:
  `0290d6ece24874287316f4bf430fef770aa4ec08a2227c8f2c1e5b2ff975e03d`.
  Its front matter identifies the US government publication as public domain.
  The downloaded source and generated traces remain outside tracked source.
- [War Cabin, Shiloh National Military Park](https://www.nps.gov/shil/learn/historyculture/upload/war-cabin-comply-2025-2.pdf):
  two physical pages, 1,055,597 bytes. SHA-256:
  `da6a4b65a0d9a919dde5ed4d6187641ef489aec3c93981768fb3ec2a949847b5`.
  A separate agent selected and read this historical narrative without seeing
  the application prompt or outputs. NPS-created content is generally public
  domain under its [published policy](https://www.nps.gov/aboutus/disclaimer.htm);
  no third-party copyright notice was seen on the rendered pages. The unchanged
  source remains outside tracked files. Its source checklist is agent-proposed,
  not a human-approved reference. Its first Folio run uses the frozen final prompt.

All runs use Docling 2.148.0, native PDF text plus English OCR; tiktoken 0.14.0;
OpenRouter's verified OpenAI standard route; maximum 4,096 output tokens and a
64,000 input estimate including a 2,048-token margin. No fallback, retrieval or
truncation. Prompt 2–3 runs use `minimal` reasoning and schema/preparation 2/2.
Prompt 4 Mini runs use `low`, schema/preparation 2/2; GPT-5.1 prompt 4 runs use
`low`, schema/preparation 2/3. The final candidate uses GPT-5.1 `low` and
prompt/schema/preparation 5/3/3.

The report produced 657 evidence elements. Its initial complete request estimate
was 94,233 tokens. Removing bounding boxes, offsets and redundant structural
fields from model input reduced the estimate to 48,918 tokens with prompt 2,
while retaining every source ID, text/table content and page reference. Detailed
provenance remains in PostgreSQL. Preparation 3 also retains non-null parent
links, such as a caption's association with its table. The initial parsing run took about 99 seconds;
this is one local observation, not a latency guarantee.

## Recorded calls

Every listed trial made one paid call. The final NIST run also claimed a second
worker attempt, which was denied admission without another paid call. Prices are
provider-reported USD, excluding account purchase fees/taxes. Unknown costs are
not treated as zero.

| Input | Model | Prompt | Input/output tokens | Reported cost | Review |
| --- | --- | ---: | --- | ---: | --- |
| Mixed PDF | GPT-5 Nano | 2 | 636 / 212 | $0.00011660 | Factual amounts/date correct, but two points describe layout and the overview overstates unavailable content. Not accepted for quality. |
| Mixed PDF | GPT-5 Nano | 3 | 673 / 153 | $0.00009485 | Two substantive, supported points; known gap retained. Overview remains wordy and focused on document structure. |
| NIST report | GPT-5 Nano | 3 | 44,897 / 795 | $0.00256285 | Broadly plausible prose, but citation support fails. |
| NIST report | GPT-5 Mini | 3 | 44,897 / 1,129 | $0.01348225 | Better source selection, but verbose and still weakens an optional operation into a recommendation. |
| NIST report | GPT-5 Mini | 4 | 45,002 / 863 | $0.01297650 | Shorter, but overstates ZTA-specific risks and still weakens qualifications or omits direct supporting references. |
| Mixed PDF | GPT-5 Mini | 4 | 778 / 488 | $0.00117050 | Natural overview, three supported points and known gap retained in a narrow source review. |
| NIST report | GPT-5.1 | 4 | 45,009 / 1,147 | $0.06773125 | Stronger source support, but overloaded points with 5–31 references and minor modal/qualification imprecision. |
| Mixed PDF | GPT-5.1 | 4 | 778 / 207 | $0.00304250 | Supported amounts/date, but incidental printed-page metadata returned. |
| NIST report | GPT-5.1 | 5 | 45,043 / 4,096 | $0.09726375 | Output allowance exhausted; incomplete response rejected. Retry could not reserve within the document cap. No published summary and no quality pass. |
| War Cabin | GPT-5.1 | 5 | 2,043 / 626 | $0.00881375 | Saved summary and working citations; final source-review findings below. |

Prompt 3 adds a general instruction to use a natural overview, exclude incidental
layout metadata and never infer that unextracted pages are empty. No budget,
renewal or NIST facts were added. The mixed PDF is a development/retest case;
NIST was the next larger case, not a human-approved held-out benchmark.

## Why valid citations were insufficient

The Nano report summary's migration point cited evidence on physical pages
24–26 about enclave, resource-portal and sandbox deployment. The migration
discussion supporting incremental/hybrid adoption is on page 45, with planning
and risk material on page 46. Its overview listed exactly 100 source IDs,
including 39 headers/footers, while omitting passages needed for several claims.
Other points also attached partly relevant evidence without supporting every
clause. The application correctly resolved those IDs; that did not establish
semantic support.

This result motivates a controlled model comparison with the same generic
prompt. Restricting citation counts or checking that IDs exist cannot repair
unsupported claims by itself. A stronger model's output still needs source review.

Mini with the same prompt and minimal reasoning cited the correct migration
section, but its overview was 148 words with 78 references. It called an optional
reporting-only operation an initial recommendation and omitted qualifications
from that claim. It was not treated as a clean pass. Prompt 4 adds general
60-word/35-word overview/point targets, directly supporting citations and explicit
preservation of optional versus required language. A later trial also changes
reasoning to `low`; its result cannot isolate the effect of the prompt from the
effect of reasoning. No document-specific facts are added to either prompt.

GPT-5.1 with prompt 4 improved support on the report, but long inventories still
made the result hard to inspect. Prompt 5 asks for one central idea per point and
the smallest sufficient citation set. Schema 3 caps references at eight per
statement. The model must narrow a claim, never silently lose necessary support;
Folio rejects lists above that cap. This format guard does not prove entailment.
The prompt was then frozen before final NIST and unseen historical-document runs.
No further tuning uses those final outputs in this checkpoint.

The owner raised the original $0.10 document allowance to $0.40, retaining the
$1 deployment allowance. No Luna call was made: its initially quoted reservation
omitted automatic cache writes, whose verified bound exceeded $0.40. The selected
GPT-5.1 route reserves $0.38096; the actual settled bill is normally lower. The
ten calls cost **$0.20725480**, confirmed against PostgreSQL and OpenRouter's
read-only authentication metadata; remaining provider allowance was $0.79274520.
No cost was unknown or still reserved. Reloading the actual summary did not
create a new run or charge.

## Frozen final candidate

The 59-page report parsed in 102.58 seconds. Its complete input fitted admission,
but the provider exhausted 4,096 output tokens. Read-only generation metadata
confirmed `finish_reason=length` and `native_finish_reason=max_output_tokens`.
Folio rejected the incomplete output; the $0.09726375 known bill plus a new
$0.38096 reservation exceeds the $0.40 document cap, so retry admission correctly
ended unavailable without another request. The original and 657 evidence elements
remained accessible. This verifies a failure boundary, not successful large-input
summarization. A larger context window alone does not ensure a complete answer.

The unseen two-page bulletin parsed in 9.98 seconds and produced a saved overview
plus five points in one call. Its relevant prose and source-page mappings remained
readable; noisy OCR from signs/photos was also retained. Browser inspection checked
the actual summary, page-2 navigation, reload and 390-pixel wrapping. The final
large-report screen retained evidence, pagination and original-page navigation
while displaying the spending-limit result. The minimal UI shows the final reason;
the preceding invalid response is retained in attempt history, not explained on
that screen. The embedded PDF remains small at narrow widths.

Independent source review found the unseen answer broadly grounded, but **not a
clean semantic pass**:

- The overview says “relocations,” although the source describes one move.
- The last point groups the 1930s, 1962 and 2003 renovations under reuse of
  original logs. The source establishes that reuse specifically for the 1930s
  work, not all three renovations.
- Saying the cabin “hosted” troops blurs the source's more precise account of
  bivouacking in Perry Field; it does not establish accommodation inside the cabin.

These are generation errors, not missing source prose: Folio retained the
two-column narrative and page mappings. Incidental logo/photo OCR noise and a
lost Hamburg–Savannah hyphen were separately observed. Some points also exceeded
the prompt's 35-word target, which is guidance rather than a schema constraint.
Valid JSON and working citations did not catch these semantic errors.

The software slice is implemented and checked, but this candidate has not earned
a general quality pass or a successful final large-report result. Keep those
limitations visible at the owner checkpoint. Review actual claims and choose the
next model/configuration experiment before expanding into retrieval; do not turn
these document-specific corrections into production prompt rules.

## Reproducing and reviewing

Use the local UI/API to upload the public PDF under an explicitly budgeted
summary configuration. Read the saved summary, open each citation and compare
the whole associated claim with the source. Check qualifications and important
omissions separately. Reopening the same document must reuse its saved summary;
changing model/prompt settings does not regenerate it. Deliberate comparisons
in this increment use fresh uploads, preserving previous results and costs.

Keep software checks separate: controlled provider responses test persistence,
duplicate delivery, budgets, failures and UI behavior. They do not validate
summary quality. A broader human-reviewed set across document genres, including
contradictions and embedded instructions, remains necessary before broader claims.
