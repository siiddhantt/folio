# Folio

Understand your documents. Check the evidence.

Folio turns uploaded PDFs into inspectable evidence: text, tables, physical-page references,
and visible extraction limitations. Summaries and grounded conversations will build on that evidence.

## Current state

The first ingestion slice runs locally in Docker. FastAPI accepts a PDF, PostgreSQL records
durable work, RQ/Redis delivers it, and a Docling worker publishes evidence. Native text and
English OCR are supported; encrypted inputs receive a clear error. Recoverable partial
content remains available. A minimal React interface supports upload, processing status,
text/table evidence and the original PDF. An opt-in development view shows real processing
history. Summaries, chat and embeddings are not implemented.

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
services with `docker compose up -d`, and open **Development details** on a document.
The inspection endpoint defaults to disabled. See the [hands-on walkthrough](docs/interface-walkthrough.md).

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

## Design and development

- [Requirements](docs/requirements.md): user outcomes, acceptance criteria, constraints, and deferred capabilities.
- [Decisions](docs/decisions.md): options, tradeoffs, recommendations, and acceptance status.
- [Current status](docs/status.md): what is complete and what comes next.
- [Agent instructions](AGENTS.md): collaboration, verification, and development boundaries.
- [Skills](docs/skills.md): selected workflows, pinned upstream sources, and licenses.
- [Configuration](docs/configuration.md): supported environment values and their meaning.
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
