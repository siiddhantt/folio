# Folio

Understand your documents. Check the evidence.

Folio turns uploaded PDFs into inspectable evidence: text, tables, physical-page references,
and visible extraction limitations. Automatic cited summaries build on that evidence;
grounded conversations remain a later slice.

## Current state

The first ingestion slice runs locally in Docker. FastAPI accepts a PDF, PostgreSQL records
durable work, RQ/Redis delivers it, and a Docling worker publishes evidence. Native text and
English OCR are supported; encrypted inputs receive a clear error. Recoverable partial
content remains available. A minimal React interface supports upload, processing status,
text/table evidence and a locally rendered original page. Content and Original
sit side by side on desktop and use tabs on mobile. Compact coverage notices
retain known gaps without overwhelming the reading view. An opt-in Activity panel
shows real processing history; the configuration console saves controls for new uploads.
Automatic summaries are implemented with checked persistence, budget and failure
contracts. The current configuration completed summaries of three tested PDFs,
including a 59-page report, without exhausting output. Source review still finds
citation and qualification weaknesses; no general quality pass is claimed. Generation defaults to disabled.
Chat and embeddings remain deferred.

## Run locally

With Docker Compose installed, build the pinned parser/model image, then start Folio:

```sh
docker build -t folio-docling:2.148.0 experiments/ingestion/docling
docker compose up --build -d --wait
```

The first parser build downloads model assets and can take several minutes. Processing uses
those bundled assets locally; no inference API key is needed for ingestion.

Open [Folio](http://localhost:3000) and choose your PDF. The document URL survives reload;
processing continues after leaving the page. Light/dark themes and source-page links help
inspect the recovered content. No sample documents or simulated workflows are built in.

For local inspection, set `FOLIO_DEVELOPMENT_MODE=true` in your existing `.env`, recreate
services with `docker compose up -d`, and open **Activity** on a document.
The header control beside the theme toggle opens [development settings](http://localhost:3000/development/settings).
Saves survive restarts and apply to new uploads, including their later summaries.
The development routes default to disabled. See the [hands-on walkthrough](docs/interface-walkthrough.md)
and [console behavior](docs/development-console.md).

The [interactive API documentation](http://localhost:8000/docs) remains available. Upload one PDF using
`POST /documents`, a fresh `Idempotency-Key` header and the `file` field. Follow the returned
`status_url`, then inspect `/revisions/{revision_id}/evidence` when processing succeeds.
The same key and same input replay the original IDs; changed input with that key returns `409`.

```sh
uv sync --locked
uv run python scripts/smoke.py
```

The smoke check uses only committed synthetic PDFs. [Development and verification](docs/development.md)
explains the tests, fault exercises and limitations. Copy `.env.example` to `.env` only when
creating a new configuration; preserve an existing local file. `.env` is ignored by Git.

Automatic summaries require an explicitly enabled saved summary setting and a worker-side
OpenRouter key. `FOLIO_SUMMARY_ENABLED` seeds the setting on first use; subsequent changes
use the development console. When enabled for an upload, its usable extraction schedules one saved
summary from all available evidence. Oversized inputs remain readable with a summary
unavailable reason. Reads never generate, and enabling summaries does not backfill old
revisions. The persistent allowance is $1 total and $0.40 per document, including retries
and uncertain calls. See [summary behavior and source reading order](docs/summaries.md)
and [configuration](docs/configuration.md) before enabling generation. Local evaluation
is enabled with DeepSeek V4.1 Flash 1017 through OpenRouter/Together, reasoning
`none`, a fixed 16,384-token completion ceiling and prompt/schema/preparation
versions 6/4/3; the template remains disabled. [Recorded live calls](docs/summary-evaluation.md)
separate completion, spending and source correctness. The latest three calls
cost $0.016125504; cumulative measured spending is $0.223380304 with no unknown
billing. These small development comparisons do not establish general accuracy.

For the summary source walkthrough, read [preparation.py](src/folio/summaries/preparation.py),
[processing.py](src/folio/summaries/processing.py), then [lifecycle.py](src/folio/summaries/lifecycle.py)
alongside the [summary contract](docs/summaries.md). Preparation decides what evidence
the model sees; processing coordinates the call; lifecycle owns reservations and saved
outcomes. As a reading exercise, trace a provider timeout: identify why its reservation
stays charged against the allowance and why a late worker cannot replace a newer result.

## Design and development

- [Requirements](docs/requirements.md): user outcomes, acceptance criteria, constraints, and deferred capabilities.
- [Decisions](docs/decisions.md): options, tradeoffs, recommendations, and acceptance status.
- [Current status](docs/status.md): what is complete and what comes next.
- [Agent instructions](AGENTS.md): collaboration, verification, and development boundaries.
- [Skills](docs/skills.md): selected workflows, pinned upstream sources, and licenses.
- [Configuration](docs/configuration.md): supported environment values and their meaning.
- [Development console](docs/development-console.md): saved controls for new uploads and reproducible experiments.
- [Summaries](docs/summaries.md): automatic complete-input behavior, citations, spending and source walkthrough.
- [Interface contract](docs/interface.md): the small document workflow, design and verification boundaries.
- [Interface walkthrough](docs/interface-walkthrough.md): follow a real upload through the UI and backend.
- [Ingestion investigation](docs/ingestion.md): parser research, local comparison, and source-preservation findings.
- [Ingestion system design](docs/ingestion-system.md): upload flow, queue/storage choices, schema, retries, and the first implementation slice.
- [Code and system-design walkthrough](docs/system-design-walkthrough.md): transactions, indexes, worker coordination and scaling through actual source files.
- [AI use](AI_USAGE.md): how agents contribute and how their work is checked.

Development proceeds through small vertical slices. Each slice should deliver a complete observable behavior, meaningful verification, and an explanation of its design.

The web interface and API are exposed only on localhost. Runtime files and database state live in Docker volumes.
This is a single-host setup with local development credentials; it does not provide authentication,
off-machine backup, online artifact cleanup or a measured production capacity guarantee.
