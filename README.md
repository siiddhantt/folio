# Folio

Upload a PDF, ask questions about it, and check the passages behind each answer.

Folio reads native PDF text and English scans, saves a cited summary, and supports
follow-up questions in a saved conversation. The reader puts extracted content
beside the original page. Chat sources open the supporting passage and its page.
Known extraction gaps stay visible.

## Run it

Install Docker Compose. Copy `.env.example` to `.env` if you do not already have
one, then build the parser image and start the services:

```sh
docker build -t folio-docling:2.148.0 docker/docling
docker compose up --build -d --wait
```

The first build downloads local parsing/OCR models and can take several minutes.
Open [Folio](http://localhost:3000) or the [API docs](http://localhost:8000/docs).
Upload a PDF; **Runs** reopens its processing history. Conversations have their
own sidebar, generated titles, rename and remove controls.

Parsing needs no inference API key. Paid processing is disabled in the template.
To enable summaries, indexing and chat, follow the
[configuration guide](docs/development.md#configuration). Keep credentials in the
ignored `.env`; never put them in frontend configuration.

With `FOLIO_DEVELOPMENT_MODE=true`, **Activity** shows attempts, timing, failures
and model usage. The header settings control edits saved document/summary limits
for new uploads. Changes do not rewrite queued work or existing results.

## How it works

FastAPI saves processing intent in PostgreSQL. RQ/Redis delivers work to separate
document, chat and history workers. Docling preserves text, tables and physical
page references; its chunker prepares source-linked passages. Embeddings live in
pgvector alongside the document metadata. Each chat searches one pinned index.

Answers, follow-up interpretation and history notes can independently use
OpenRouter or direct OpenAI through the supported GPT-5.2 profile. Summaries use
DeepSeek through OpenRouter; embeddings use `text-embedding-3-small` through
OpenRouter. These routes have separate configuration. Long chats keep their full
transcript and use shorter notes for older exchanges when needed.

The React/TypeScript interface uses Vite, shadcn/Radix controls and a local PDF
renderer. The composer stays below a scrolling transcript; Enter sends and
Shift+Enter adds a line. There are no seeded runtime documents or canned answers.

## What to expect

The latest [evaluation](docs/evaluation.md) followed one new 56-page document
through upload, summary, indexing and twelve questions, including real history
compaction. It found useful table answers and retained corrections, but also
retrieval misses and citation-attribution errors. A completed model call is not
proof that its answer is supported.

PDFs are the supported input; chats cover one document. Oversized summaries report
their limit instead of silently using only the beginning. Streaming, other file
formats and multi-document chat are deferred. Aggregate statistics/metrics APIs,
some OpenAPI response schemas and the recorded walkthrough remain unfinished.

Compose exposes the interface and API on localhost. It has no authentication or
tenant isolation, and uses local credentials and named volumes. Public hosting
needs access controls, backups and measured capacity. Removing volumes deletes
documents, history and the usage ledger.

## Work on Folio

See [development](docs/development.md) for configuration, isolated tests and
debugging, and [architecture](docs/architecture.md) for the data flow, recovery and
source reading order. [Requirements](docs/requirements.md),
[decisions](docs/decisions.md) and [status](docs/status.md) track scope and remaining
work. [AGENTS.md](AGENTS.md), [AI use](AI_USAGE.md) and
[pinned skills](docs/skills.md) describe how changes are made and reviewed.
