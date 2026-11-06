# Folio

Understand your documents. Check the evidence.

Folio is being designed to turn uploaded documents into useful summaries and conversations with verifiable source references. Its central promise is a traceable path from a question to the passages supporting an answer.

## Current state

Requirements and design decisions are under discussion. Application code and a runnable service are not yet available. Proposed features and architecture are not claims of implemented behavior.

## Design and development

- [Requirements](docs/requirements.md): user outcomes, acceptance criteria, constraints, and deferred capabilities.
- [Decisions](docs/decisions.md): options, tradeoffs, recommendations, and acceptance status.
- [Current status](docs/status.md): what is complete and what comes next.
- [Agent instructions](AGENTS.md): collaboration, verification, and development boundaries.
- [Skills](docs/skills.md): selected workflows, pinned upstream sources, and licenses.
- [Configuration](docs/configuration.md): supported environment values and their meaning.
- [AI use](AI_USAGE.md): how agents contribute and how their work is checked.

Development proceeds through small vertical slices. Each slice should deliver a complete observable behavior, meaningful verification, and an explanation of its design.

Runtime setup instructions, examples, and a document-chat demonstration will be added with working code. Credentials and user documents do not belong in source control.
