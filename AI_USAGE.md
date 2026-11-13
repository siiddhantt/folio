# AI use in Folio

AI agents assist research, design comparisons, implementation, testing and review.
Siddhant owns scope, architectural choices and acceptance. Agents do not turn
research recommendations into product decisions without that acceptance.

Work proceeds through small vertical slices: define observable behavior, agree
the boundary, write a meaningful failing test, implement, verify and obtain an
independent review. Delegated work has owned files and exclusions. The integrator
checks contracts and explains the data flow and failure paths to the owner.

Deterministic tests use controlled model responses to check persistence,
recovery, scope and accounting. Live evaluations use actual providers and compare
retrieved and cited passages with the original source. Agent review supplements
executable checks and human judgment; it does not establish universal correctness.

## Contributions and checks

| Area | Agent contribution | Evidence and limits |
| --- | --- | --- |
| Ingestion | Compared Docling/LiteParse, implemented durable upload/evidence/recovery and source inspection | Synthetic parser/API checks and interruption exercises. Docling preserved stronger table relationships in the comparison; both parsers missed a damaged-page signal. |
| Summaries/indexing | Built bounded complete-input summaries, source-linked chunks, embedding checkpoints and accounting | Persistence/failure tests plus live source review. Completed summaries still show citation and qualification weaknesses. |
| Conversations | Built saved answers, follow-up resolution, history notes, UI and separate OpenRouter/OpenAI adapters | Real database tests, controlled provider tests and browser checks. Model choice followed limited source-reviewed examples, not a broad benchmark. |
| Review | Separate agents challenged scope, stale-worker publication, configuration snapshots and billing | Review caught concrete defects, including service/profile inheritance and preflight omissions. Passing checks do not replace ongoing failure analysis. |
| November 13 evaluation | Selected a public guide, prepared source expectations before seeing outputs, drove one UI upload/chat, inspected logs and independent source support | Twelve real turns and one background compaction. The [report](docs/evaluation.md) records retrieval misses and attribution errors as well as working behavior. |
| Documentation | Consolidated current behavior, removed superseded walkthroughs and applied a pinned prose-editing skill | Preserved guardrails, provenance, limitations and historical evidence in Git. No claim that AI-assisted prose was human-authored. |

[AGENTS.md](AGENTS.md) contains collaboration rules; [skills](docs/skills.md)
records reviewed sources, licenses and invocation boundaries. Prompts and schemas
live with their feature modules and have explicit versions. Raw conversations,
credentials, uploaded files and local evaluation traces are not tracked.

The detailed earlier development record remains in
[Git history](https://github.com/siiddhantt/folio/blob/1c793a9891e4aaf833acce53987eb7ee1beee3e0/AI_USAGE.md).
Current capability and remaining work belong in [status](docs/status.md).
