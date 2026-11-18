# AI use in Folio

AI agents assist research, design, implementation, testing and review. Siddhant
owns scope and architectural decisions. Research recommendations do not become
product decisions without acceptance.

On November 19 an agent prepared page-checked retrieval labels, ran the
budgeted shortlist and chunk-size comparison, and implemented the local
same-page grouping option. A deterministic source-link test and a comparison
against the original experiment's 318 grouped passages verified the indexing
change. Human review of the labels and broader generalization remain open.
[Measured outcomes](docs/evaluation.md#november-19-shortlist-and-chunk-size-comparison).

Work proceeds through small behaviors: agree the outcome, write a meaningful
failing test, implement, verify and obtain an independent review. Delegated tasks
have owned files and exclusions; one integrator checks contracts and scope.
Controlled model responses test software behavior. Live evaluations separately
compare retrieved passages and generated claims with the original documents.

## Contributions and verification

| Area | Agent contribution | Evidence and limits |
| --- | --- | --- |
| Ingestion and persistence | Compared Docling/LiteParse and built upload, evidence, recovery, summaries and checkpointed indexing. | Parser/API tests and interruption exercises passed. Docling preserved stronger table relationships in the comparison, but both parsers missed a damaged-page signal. Summary citation weaknesses remain. |
| Conversations | Built saved answers, follow-up interpretation, history notes, citations and provider adapters. | Database, controlled-provider and browser checks cover the workflow. A twelve-turn live evaluation exercised one background compression and exposed retrieval misses and mixed history/PDF attribution errors. |
| Monitoring APIs | Added document statistics, processing aggregates and typed public response schemas. | HTTP/PostgreSQL checks cover retries, removed chats, batch counts and missing timing. Independent review checked query semantics and compatibility. |
| Direct OpenAI routes | Added direct summaries/embeddings, estimated billing and grouped environment documentation. | 29 summary checks, 22 embedding/query checks and two billing browser checks passed. Review found and fixed SQL typing, settled-metadata and billing-display defects. Older policies and recorded spending were preserved. |
| Retrieval diagnosis and experiments | Reconstructed saved prompts, inspected vector/source association and built one runner for grouping, MiniLM, Jev and correct-source generation. | Grouping and Jev each recovered 7/7 facts on one source; baseline and MiniLM recovered 5/7. On two further PDFs, all four arms initially retrieved 17/18 facts. A missing caption and seven rejected cited responses exposed separate indexing/validation defects. No production default changed. |
| Caption and partial-answer fixes | Added failing regressions, preserved older policies and reran the frozen questions with independent source review. | 64 targeted checks passed. Each of four methods retrieved 18/18 facts and gave 8/8 complete positive answers; both negative controls abstained. All 40 outputs validated and 114 paid responses replayed unchanged. A browser rehearsal verified follow-ups, citations and reload. This small regression set does not establish general accuracy. |
| Interface | Refined the home screen, automatic history refresh and Back controls in page headings. | 23 affected browser checks and 12 navigation/composer checks passed. Review caught focus loss during history retry, fixed with a regression. Responsive, keyboard, theme and zoom checks passed; screen-reader testing was not performed. |
| Docker and notebook | Prepared reproducible setup, a checkpointed API walkthrough and an optional native ARM64 document worker. | Five Mac PDF smoke checks passed. The native worker matched 116 package versions and nine model files, with 58 offline checks and five HTTP smoke checks. A full notebook rerun created no duplicate work or charges. No capacity claim follows. |
| Documentation and release review | Condensed setup/current status, added a small README mark, applied the pinned Humanizer skill and independently reviewed the publication diff. | Ruff lint/format, frontend typecheck/build/format and document links passed. The README was previewed at desktop/mobile widths. Notebook metadata was restored to Python 3.12, with outputs clear; the credential scan found no matches in public files. Known failures, skill provenance and AI attribution remain documented. |

Independent review found concrete defects in stale-worker publication,
configuration inheritance, preflight checks and billing. It complements tests and
human judgment; neither passing tests nor valid citation IDs prove answer support.

## Records and boundaries

[Evaluation](docs/evaluation.md) records methods, source expectations, versions,
latency, actual outcomes and cost estimates, including failed examples. The latest
fix/ingestion/rehearsal increment cost $0.215439914 in estimates. Completed paid
responses replay from local receipts; no mocked answer is reported as AI quality.
Source labels are agent-curated unless explicitly described otherwise.

Prompts and schemas live with their feature modules and carry explicit versions.
Credentials, uploaded documents, private conversations and raw evaluation traces
remain outside tracked source. [AGENTS.md](AGENTS.md) defines collaboration rules;
[pinned skills](docs/skills.md) records sources, licenses and invocation boundaries.

Current capabilities and unresolved work are in [status](docs/status.md).
[Decisions](docs/decisions.md), [evaluation](docs/evaluation.md) and the
[earlier AI-use record](https://github.com/siiddhantt/folio/blob/1c793a9891e4aaf833acce53987eb7ee1beee3e0/AI_USAGE.md)
preserve the detailed development history.
