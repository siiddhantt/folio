# Folio ingestion investigation

Updated November 6, 2026. The local Docker comparison is complete. Docling and PDF inputs with English OCR are selected; DOCX is deferred. This document separates source claims from observed results.

## Decisions and responsibilities

Use recoverable content with explicit known-coverage warnings. Partial extraction should not disable all summaries or chat. If a requested fact is unavailable, distinguish not finding it in the extracted content from proving it absent in the original document. Summaries of partial content must not imply full coverage. No usable content means no document-grounded factual answer.

Develop locally with Docker. Accept PDFs with English OCR available for scanned content; retain usable partial extraction and expose known coverage limitations. DOCX and other formats are deferred. Accepting an engine with a long format list does not automatically make every format a supported Folio feature.

Reuse established software for PDF decoding, OCR, layout recognition, tables, and format conversion. Folio still owns uploaded-file identity, processing attempts, user-visible status, coverage warnings, storage, document scope, and source-backed answers. Existing queue and database libraries provide infrastructure, but they cannot choose these product rules.

Proposed integration:

```mermaid
flowchart LR
    U[Upload] --> F[Store original and pending record]
    F --> Q[Existing task queue]
    Q --> W[Folio worker]
    W --> P[Chosen ingestion engine]
    P --> E[Text, tables, source locations, diagnostics]
    E --> S[Persist processing revision and known coverage]
    S --> R[Search, summaries, and chat]
```

The engine can run as a library inside the worker container. Docling-serve is an alternative packaged internal API with Compose and queue support; avoid adding its orchestration beside another queue without a clear ownership reason. [Docling-serve deployment](https://docling-project.github.io/docling/usage/api_server/deployment/).

## Shortlist

| Tool | Why consider it | What still needs verification |
| --- | --- | --- |
| Docling 2.148.0 | Learned layout/table processing, multiple formats, local OCR, structured document model, partial-success/error records | Actual reading order, table relationships, page/source granularity, CPU memory, model startup and undetected omissions |
| LiteParse 2.18.0 | Native Python/Rust package, spatial PDF text, OCR integration, page errors/diagnostics, optional Office conversion | Table reconstruction, failed-OCR diagnostics, native versus rendered source locations, and package/converter requirements |
| Unstructured OSS | Broad format partitioning, native/OCR/layout strategies and element metadata | Different fallback behavior across modes; a uniform recoverable per-page contract was not established in this review |
| Managed LlamaParse | Outsourced execution, OCR, structured output and page results | Additional account/data transfer/cost, provider failure semantics, and service dependency; this is distinct from local LiteParse |

Docling exposes partial conversion results and page-range processing. LiteParse exposes continuation after page errors and selected-page processing. These capabilities help implement partial availability; neither is proof that all missing content will be detected. Sources: [Docling converter](https://docling-project.github.io/docling/reference/document_converter/), [LiteParse Python API](https://github.com/run-llama/liteparse/blob/main/packages/python/README.md), [Unstructured partitioning](https://docs.unstructured.io/open-source/core-functionality/partitioning), [LlamaParse configuration](https://developers.llamaindex.ai/llamaparse/parse/guides/configuring-parse/).

Docling's code is MIT; the selected layout/table model repositories have separate licenses. LiteParse is Apache-2.0, with separate OCR language data and system-converter dependencies. Record the actual assets used by the comparison rather than assuming a code license covers every downloaded weight. [Docling model catalog](https://docling-project.github.io/docling/usage/model_catalog/), [LiteParse source](https://github.com/run-llama/liteparse).

Kreuzberg/Xberg was also reviewed. The 2026 rename and backend/API changes mean older Kreuzberg benchmarks do not establish the current engine's behavior. It is not included in this two-tool comparison. [Migration and changelog](https://docs.xberg.io/changelog/).

## What practitioner sources establish

- **Thoughtworks, April 15, 2026:** moved Docling to its Trial ring after reporting useful production-scale extraction across digital and scanned documents. This is first-hand consultancy experience, not an industry-wide survey or a Folio benchmark. [Radar entry](https://www.thoughtworks.com/radar/languages-and-frameworks/docling).
- **Dennis Adriaansen, October 27-28, 2026:** demonstrated PyMuPDF/OCR for simpler documents and Docling for complex ones in Nuxt Agentic. His reply describes selecting the route through experimentation. The author builds the demonstrated product; this is a practical example with a commercial interest, not a controlled comparison. [X demonstration](https://x.com/DennisAdriaans/status/2115086407626842257), [routing reply](https://x.com/DennisAdriaans/status/2115331458663645654).
- **LlamaIndex, November 6, 2026 local display:** announced a LiteParse/MiniCPM-OCR integration and linked implementation. This supports extensible OCR as a real integration path. Its accuracy/speed comparisons are vendor claims and are not adopted as Folio results. [X announcement](https://x.com/llama_index/status/2118433203526533150).
- **Table-extraction experiment, September 22, 2026:** a small public example shows how changing headers/gridlines can break semantic table associations across parsers. The author discloses freelance promotion; the inspectable inputs are more useful than a generalized ranking. [Forum discussion](https://www.reddit.com/r/dataengineering/comments/1wm9fbk/a_misplaced_header_is_enough_to_make_pdf_table/), [scripts and inputs](https://github.com/gnatale/table_extraction_blog).
- **Docling native-parser issue, September 8, 2026:** reports large memory use from dense vector content with versions and a synthetic reproducer. These are reported measurements for that workload, not our measurements or a prediction for ordinary PDFs. It motivates resource limits and visible worker failures. [Issue](https://github.com/docling-project/docling-parse/issues/345).
- **Docling table provenance discussion, January 2026:** a contributor and maintainers discuss cell-level locations in combined tables. The proposed change is not evidence that every released version has cell-level page references. Inspect actual output before promising that precision. [Discussion](https://github.com/docling-project/docling-core/pull/467).

Together these sources support reusing an engine and evaluating meaningful output. They do not establish a single universally preferred ingestion stack.

## Local comparison contract

The [fixture generator](../experiments/ingestion/make_fixtures.py) creates synthetic text, scanned and mixed PDFs, grid/borderless tables, a deliberately damaged page, and DOCX. Expected content is stored separately from the directory mounted into parser containers. No personal documents or model credentials are supplied to either parser.

Use the same fixture bytes, four CPU cores, six GiB memory limit, and one parser container at a time. Build/model downloads are setup work, outside timed parses. Runtime networking is disabled. Both run an initial conversion followed by two warm repeats; retain every outcome and distinguish initialization from warmed work. This tiny fixture set can expose integration problems, not justify a general speed/accuracy ranking.

Inspect correct facts, physical page references, table row/column associations, OCR recovery, blank-page behavior, reported gaps, and source locators for converted Office files. A Markdown string containing all numbers is insufficient evidence of a correct table. A successful return is not a guarantee of complete semantic extraction.

The damaged fixture uses an unsupported content-stream filter on its middle page. Poppler renders that page blank with diagnostics. Observe parser behavior rather than assuming the corruption must raise a page exception. Its erased text is not expected to be reconstructed; neighboring readable pages should be inspected separately.

Memory measurements must state whether they are process high-water marks, terminated-child high-water marks, sampled container usage, or cgroup peak. Do not add unrelated process peaks and label the result simultaneous usage. Record image identity, versions, OCR settings, selected assets, and fixture hashes.

## Results

Both engines completed all 18 attempts (36 total), with container exit code zero and no OOM. Input hashes match the reference manifest. Extracted content and source structure were stable across all three attempts. The fixtures were generated by an agent, rendered and inspected, then checked against both outputs by a separate reviewing agent; this was not a blinded human benchmark.

| Source behavior | LiteParse 2.18.0 | Docling 2.148.0 |
| --- | --- | --- |
| Text, scanned, and mixed PDFs | All expected facts on correct physical pages | All expected facts on correct physical pages |
| Printed versus physical page | Reports the scan at physical page 2 in the mixed document, despite printed page 7 and an old footer saying page 1 | Same |
| Ruled table | Correct data cells, with headings separate from the table | Exact headers and row/column associations |
| Borderless table | Spatial page text preserved, but no structured table; flattened paragraph blocks separate row labels from values | Exact headers and row/column associations |
| Damaged middle page | Neighboring facts preserved; damaged page empty, no page error | Neighboring facts preserved; damaged page empty, no structured error |
| DOCX | Correct contents through LibreOffice; locations belong to an ephemeral rendered PDF | Correct native text/table structure with parsed-item references, without page/bounding-box provenance |

Neither engine identified this damaged page reliably. Docling's poor/zero confidence for it also appears on the genuinely blank page; LiteParse's no-text/needs-OCR diagnostics likewise fail to distinguish them. A successful parser result or confidence value cannot certify completeness. Docling additionally logged orientation-detection and empty-confidence warnings despite structured `errors=[]`; the expected scan facts still survived.

### Measured resources

Seconds per complete file, median of the two warm repeats:

| Fixture | LiteParse | Docling |
| --- | ---: | ---: |
| Text PDF, 3 pages | 0.228 | 3.960 |
| Scanned PDF, 1 page | 0.140 | 1.969 |
| Mixed PDF, 3 pages | 0.208 | 4.617 |
| Table PDF, 2 pages | 0.146 | 4.004 |
| Damaged PDF, 3 pages | 0.187 | 4.008 |
| DOCX | 0.660 | 0.023 |
| Whole-run container peak, MiB | 412.95 | 1481.85 |

These are two specific CPU configurations: one configured Docling compute thread versus two LiteParse OCR workers/OpenMP threads, inside equal four-CPU/six-GiB container ceilings. Files ran serially, with networking disabled. Memory is the cgroup-v1 whole-container high-water mark, including children and charged cache, not per-file RSS or a production sizing recommendation. DOCX conversion is included in LiteParse's timing; Docling reads DOCX natively.

The first process-cold conversion, `damaged.pdf`, took 0.245 seconds in LiteParse and 6.993 in Docling. Startup was measured separately: 0.575 seconds from LiteParse runner start to ready, and 3.211 seconds for Docling converter imports/construction. Those startup scopes differ; lazy Docling model loading also occurs during the first conversion. Downloads/builds and result serialization are excluded from conversion times. No OS-cache eviction or large-document/concurrent-load trial was performed.

Reproduction commands are in the [experiment README](../experiments/ingestion/README.md). The [measurement record](../experiments/ingestion/results-2026-11-06.json) preserves all attempt timings, fixture hashes, image identities, adapter hashes, and review findings. Detailed raw outputs, environment/model manifests, and logs remain local under the ignored `tmp/ingestion/verified-results/` directory. No cloud inference or embedding calls were made.

### Selected direction and remaining decisions

**Docling is selected as the first parser.** It preserved the two table structures without additional reconstruction code, which matters when a question asks for a department's value in a particular year. Its measured local processing and memory costs are higher for these PDFs. LiteParse remains an alternative to reconsider if simpler text documents and a smaller runtime become the priority. A dual-parser router has not earned its complexity.

**PDFs with English OCR are accepted for the initial input boundary; DOCX is deferred.** These clean English scans establish feasibility, not quality for noisy, rotated, handwritten, multilingual, or complex graphical documents. Add representative examples before promising those cases. DOCX works at the content level, but its source-inspection experience remains a later decision. File/page/time limits and encrypted-file behavior are still open.

Folio's proposed integration should preserve text, structured tables, physical PDF pages, source boxes and their coordinate origins, parsed-item references, parser/configuration versions, and diagnostics. Docling table data is separate from its text items: indexing only the convenience `text` field would discard the very tables this comparison favors. In these results, table boxes use `BOTTOMLEFT` while cell boxes use `TOPLEFT`; a source viewer must normalize coordinates correctly. This is a small application boundary around one engine, with no second adapter planned yet.

Usable evidence should remain available. Record pages with no recovered text without asserting that they are corrupt or scanned; retain specific failures when actually reported. Known partial summaries must state their coverage. No parser evaluated here guarantees that every omission will be detected.

### Verification and setup corrections

The comparison adapter initially overwrote parser diagnostics if export failed. A focused emitted-artifact test reproduced that failure before the fix, then passed with parser diagnostics retained separately from adapter errors. Both adapter-contract tests and the offline Docling constructor check passed; they verify the measurement boundary, not general extraction quality.

The first Docling build's dated Debian mirror stalled; ordinary mirrors succeeded. A code-only derived image applied the adapter fix without downloading unchanged dependencies/models again. Resolved package/model versions and actual image identity were retained. Builds are not fully hash-locked or minimized. An earlier LiteParse trial missed memory capture by assuming cgroup v2; the final sequential comparison reran both engines with v1/v2-aware capture. Original and failed logs were preserved rather than substituted with successful-run claims.
