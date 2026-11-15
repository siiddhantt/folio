<p align="center">
  <img src="docs/assets/folio-mark.svg" alt="Folio document mark" width="72" height="72">
</p>

<h1 align="center">Folio</h1>

<p align="center">
  Understand your documents. Check the evidence.
</p>

<p align="center">
  <a href="#run-locally">Get started</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="notebooks/folio_demo.ipynb">Notebook</a> ·
  <a href="AI_USAGE.md">AI use</a>
</p>

Upload a PDF, read its summary, and ask follow-up questions in a saved conversation.
Every cited answer opens the supporting passage and its original page.

## What you can do

- Read native PDFs and English scans, including extracted tables and figure text.
- Explore a cited summary beside the original document, with known extraction gaps visible.
- Ask questions, follow up, and reopen conversations with their source references intact.
- Inspect background processing, timing, failures and model usage in Activity.
- Query document statistics and processing metrics through the API.

## Run locally

Install Docker with Compose, clone the repository, and create `.env` from
[`.env.example`](.env.example) if you do not already have one.

**Linux amd64 or Intel Mac**

```sh
docker build --platform linux/amd64 -t folio-docling:2.148.0 docker/docling
docker compose up --build -d --wait
```

<details>
<summary>Apple Silicon</summary>

Set `COMPOSE_FILE=compose.yaml:compose.arm64.yaml` in `.env`, then run:

```sh
docker build --platform linux/arm64 -t folio-docling:2.148.0-arm64 docker/docling
docker compose up --build -d --wait
```

The document worker runs natively on ARM64; other services retain amd64.
See [Mac setup](docs/development.md#running-on-a-mac) for details.

</details>

The first build downloads local parsing and OCR models and can take several minutes.
Open **[Folio](http://localhost:3000)** or the **[API docs](http://localhost:8000/docs)**.

Parsing works without an inference key. Summaries, indexing and chat are disabled
until configured. For the complete flow, add `OPENAI_API_KEY`, enable
`FOLIO_SUMMARY_ENABLED` and `FOLIO_INDEX_ENABLED`, and set a spending allowance in
`.env` before the first start. The [configuration guide](docs/development.md#configuration)
explains saved settings, provider routes and limits. Keep credentials in the ignored
`.env`; new work defaults to direct OpenAI.

Set `FOLIO_DEVELOPMENT_MODE=true` to inspect Activity and saved controls.
**Runs** shows processing history. The [notebook](notebooks/folio_demo.ipynb)
walks through the same APIs, from upload to chunks and a saved conversation;
[notebook setup](docs/development.md#notebook-walkthrough) covers its optional kernel.

## How it works

```text
PDF → Docling extraction → cited summary + source-linked chunks
                                               ↓
Question + conversation → pgvector retrieval → answer with page references
```

FastAPI stores work and results in PostgreSQL. Redis and RQ deliver jobs to
separate document, chat and history workers. Docling preserves text, tables and
physical-page references; pgvector stores embeddings. Long conversations retain
their full transcript and use shorter notes for older exchanges when needed.

The React/TypeScript interface uses Vite, shadcn/Radix and a local PDF renderer.
Provider settings are independent by stage, and accepted work keeps its captured
configuration. See [architecture](docs/architecture.md) for recovery, persistence
and the source reading order.

## Scope and verification

Folio supports PDFs and one document per conversation. The latest
[regression evaluation](docs/evaluation.md#november-15-caption-and-partial-answer-fix-verification)
checked two public PDFs and ten questions across four retrieval methods: each
retrieved all 18 required facts and produced eight complete supported answers
plus two appropriate abstentions. All 40 responses passed validation after the
caption and partial-answer fixes. This is a small regression set, not a general
accuracy benchmark; the default remains six vector-selected passages.

Broader retrieval quality, summary citations and mixed conversation/document
attribution still need work. Streaming, other file formats and multi-document
chat are deferred. [Status](docs/status.md) records the current limits.

Compose binds the UI and API to localhost. Authentication, tenant isolation and
production capacity are outside the current scope. Named volumes retain documents,
history and usage across restarts; removing volumes deletes that data.

## Documentation

| Read | For |
| --- | --- |
| [Development](docs/development.md) | Configuration, isolated checks and debugging |
| [Architecture](docs/architecture.md) | Data flow, workers, recovery and code navigation |
| [Requirements](docs/requirements.md) · [Decisions](docs/decisions.md) | Accepted scope and design tradeoffs |
| [Evaluation](docs/evaluation.md) · [Status](docs/status.md) | Measured results and remaining work |
| [AI use](AI_USAGE.md) · [Agent guide](AGENTS.md) · [Skills](docs/skills.md) | AI-assisted development, review and provenance |
