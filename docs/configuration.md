# Folio configuration

Folio's local `.env` is commentless and excluded from Git. `.env.example` is a safe, commentless template; it contains no usable credential.

| Name | Meaning | Current state |
| --- | --- | --- |
| `OPENAI_API_KEY` | Server-side credential for the initial AI provider | Empty until credentials are supplied locally. |

No application configuration loader exists yet. Add settings as their behavior is accepted and implemented: model IDs, connection URLs, storage locations, file limits, timeouts, retrieval settings, and usage budgets. Validate them at startup and explain defaults and units here.

Never print secrets in logs, evaluation artifacts, or error messages. Environment values containing credentials must not be exposed to a browser bundle.

Configuration makes values adjustable; it does not make every change immediately compatible. Embedding model/dimension and parsing/chunking changes can require a rebuilt index. Document those transitions before supporting a setting.

Keep schemas, prompt templates, fixtures, and dependency versions in versioned files. The environment file holds secrets and deployment/runtime values, not the entire behavior of the application.
