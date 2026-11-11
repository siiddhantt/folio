# Folio configuration

Folio's local `.env` is commentless and excluded from Git. `.env.example` is a safe, commentless template; it contains no usable credential.

| Name | Meaning | Current state |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Server-side credential for OpenRouter | Supplied locally; never commit or print its value. |
| `OPENROUTER_BASE_URL` | Base URL for the selected API gateway | `https://openrouter.ai/api/v1` |

The ingestion loader is [`Settings`](../src/folio/config.py). It validates positive bounds,
retry delays and the timeout relationship at startup. Docker Compose forwards only the
implemented settings. Only the worker receives the OpenRouter credential; it is
never passed to the API, dispatcher or browser bundle. Summaries default to disabled.

| Ingestion setting | Default / meaning |
| --- | --- |
| `FOLIO_PORT` | `8000`; Compose exposes the API on localhost only. |
| `FOLIO_WEB_PORT` | `3000`; Compose exposes the web interface on localhost only. |
| `FOLIO_DEVELOPMENT_MODE` | `false`; gates the development inspection endpoint and UI. Enable explicitly for local inspection; it is not authentication. Safe lifecycle events are recorded whether or not the view is enabled. |
| `FOLIO_MAX_UPLOAD_BYTES` | `26214400` (25 MiB); actual file bytes. Total multipart input is bounded before spooling, with 64 KiB overhead allowance. |
| `FOLIO_MAX_PAGES` | `100`; reject rather than silently truncate. |
| `FOLIO_PARSER_TIMEOUT_SECONDS` | `240`; Docling's cooperative document timeout. |
| `FOLIO_JOB_TIMEOUT_SECONDS` | `300`; RQ workhorse processing/publication budget. Native code can delay signal handling. |
| `FOLIO_WORKER_MONITOR_SECONDS` | `10`; parent supervision interval. |
| `FOLIO_LEASE_SECONDS` | `420`; permission to publish after claiming. Must exceed job timeout + 60 seconds + monitor interval. |
| `FOLIO_MAX_ATTEMPTS` | `3`; includes the initial parse attempt. |
| `FOLIO_RETRY_DELAYS_SECONDS` | `[15,60]`; JSON array of seconds. Its last value repeats if more attempts are configured. |
| `FOLIO_RETRY_JITTER_SECONDS` | `5`; random additional delay from zero to this value, persisted once. |
| `FOLIO_RECOVERY_INTERVAL_SECONDS` | `15`; dispatcher/recovery polling interval. |
| `FOLIO_DISPATCH_GRACE_SECONDS` | `30`; delivery observation/reservation grace and broker retry delay. |
| `FOLIO_BATCH_SIZE` | `20`; bounded pending/recovery scan batch, maximum 100. |
| `FOLIO_BOOTSTRAP_FAILURE_LIMIT` | `3`; distinct terminal queue failures before a processing claim. |

For processes outside Compose, `FOLIO_DATABASE_URL`, `FOLIO_REDIS_URL`,
`FOLIO_ARTIFACT_ROOT` and `FOLIO_MODELS_PATH` configure their connections/paths.
Compose deliberately supplies private-network URLs and volume/model paths. Its database
password is a public local-development default, not a production secret.

Accepted requests freeze their processing settings. Changing `.env` changes newly accepted
work after recreating services; it does not rewrite old requests. A worker rejects an old
request if its parser version or current supervision timing is incompatible. Changing parser
versions requires rebuilding the parser image and deliberately updating the pinned code.
Keep OCR language/model choices fixed to the verified English configuration for this slice.

## Automatic summary controls

[`SummarySettings`](../src/folio/summaries/config.py) validates these implemented
settings. `.env.example` and Compose default generation to disabled. Local
generation is explicitly enabled for the ongoing budgeted evaluation. Only the
worker receives `OPENROUTER_API_KEY`; no quality pass is implied.

| Setting | Default / meaning |
| --- | --- |
| `FOLIO_SUMMARY_ENABLED` | `false`; capture automatic summary policy when usable extraction is published. |
| `FOLIO_SUMMARY_MODEL_ID` | `deepseek/deepseek-v4.1-flash-1017`; fixed comparison model. |
| `FOLIO_SUMMARY_PROVIDER` | `together`; explicitly selected standard route through OpenRouter. The earlier Fireworks route remains supported, without automatic fallback. |
| `FOLIO_SUMMARY_INPUT_LIMIT_TOKENS` | `64000`; complete evidence, instructions, schema and margin must fit. |
| `FOLIO_SUMMARY_MAX_OUTPUT_TOKENS` | `16384`; generous fixed completion ceiling, not a requested visible length or automatic charge. |
| `FOLIO_SUMMARY_TOKEN_MARGIN` | `2048`; positive allowance for uncertain provider framing. |
| `FOLIO_SUMMARY_REASONING_EFFORT` | `none`; checked against model metadata. |
| `FOLIO_SUMMARY_TIMEOUT_SECONDS` | `90`; provider request timeout. |
| `FOLIO_SUMMARY_MAX_ATTEMPTS` | `2`; initial attempt plus at most one automatic retry. |
| `FOLIO_SUMMARY_BUDGET_USD` | `1.00`; persistent deployment allowance, not reset by restart. |
| `FOLIO_SUMMARY_DOCUMENT_BUDGET_USD` | `0.40`; owner-approved allowance including retries and uncertain calls. |

Current prompt/schema/preparation versions are 6/4/3. Preparation preserves
parent links alongside text/table content, source IDs and page references. Output
contains an overview and 1–5 cited points, normally 3–5 without padding short
sources. Stored coverage supplies known extraction gaps. Complete available
evidence must fit; there is no truncation, hierarchy, retrieval substitution,
manual generation or generation on reads. Enabling does not backfill old revisions.
See the [summary contract and walkthrough](summaries.md).

Runtime settings are captured when usable extraction is published. Effective
input and code versions are recorded at first admission; retries after admission
must match that manifest. A never-admitted queued run can use newer preparation
code after a deployment, so the manifest is authoritative for actual provenance.

Token admission uses the selected upstream tokenizer plus a margin. Monetary
admission reserves the route's full prompt ceiling plus maximum output, not the
estimated input bill. The selected DeepSeek route omits its separate prompt cap;
Folio conservatively reserves its combined context ceiling for input instead:
$0.3342336 at the observed rates. This is an upper bound for financial admission,
not a claim that the provider accepts that many input tokens. The smaller local
64,000-token admission limit still applies. Unknown
outcomes retain that reservation; retries require a fresh one. An uncertain
call therefore leaves insufficient room for another full reservation under the
$0.40 document cap, even with two attempts configured. Invalid summary
configuration cannot prevent usable extraction publication. The client rejects
unsupported limits, parameters and tiered pricing. Output exhaustion is terminal
with `SUMMARY_OUTPUT_LIMIT`; no adaptive retry increases the allowance. Configurability does
not establish compatibility; see [model research and retirement limits](models.md).

The DeepSeek tokenizer JSON and its MIT license are pinned to an immutable
upstream revision and verified by SHA-256 at Docker build time. Runtime counting
loads the verified asset offline. `FOLIO_TOKENIZER_DIRECTORY` sets its asset root
outside Docker; Compose images use `/opt/tokenizers`. A missing or corrupt asset
stops before paid work. JSON message/schema counting plus the margin is an
estimate: provider-specific message framing is not reproduced exactly.

## Deferred chat and embedding controls

Chat and embeddings remain deferred. The following names are proposals for later
conversation work, not settings consumed by summaries or added as inert flags to
the environment template. Their numerical defaults remain open.

| Proposed setting | Purpose |
| --- | --- |
| `AI_MODEL` | Explicit later chat model ID, to be selected and evaluated; avoid a moving latest alias. |
| `AI_INPUT_BUDGET_TOKENS` | Folio's maximum assembled input: instructions, current question, selected history, retrieved evidence, and formatting overhead. |
| `AI_EVIDENCE_BUDGET_TOKENS` | The part of the input budget available to retrieved passages and their source labels. |
| `AI_HISTORY_BUDGET_TOKENS` | The part of the input budget available to previous conversation turns. |
| `AI_MAX_OUTPUT_TOKENS` | Reserved generated-token budget, including reasoning tokens where the selected API/model counts them. It is not a requested answer length. |
| `AI_REASONING_EFFORT` | A model-specific effort choice. Validate it against the chosen model/route; unsupported values must not silently disappear. |
| `AI_TIMEOUT_SECONDS` | Maximum wait for a provider response; retries require a separate, bounded policy. |

An embedding model and its dimensions need separate settings when retrieval is designed. They must not inherit the generation model identifier.

The provider's model/endpoint context limit is a capability to verify, not a capacity that Folio can enlarge by changing an environment variable. The proposed budget invariant is:

`assembled input + reserved generated tokens + safety margin <= verified context limit`

Also enforce the selected route's separate ceilings: assembled input must not exceed its maximum prompt tokens, and the output reservation must not exceed its maximum completion tokens. Passing the combined-context check alone is insufficient. If route metadata omits a limit, verify it before relying on that capacity rather than interpreting the missing field as unlimited.

The evidence and history budgets are parts of the input budget, not additional capacity. The current question, instructions, citation labels, and message-format overhead also need room. Token accounting must match the selected model as closely as supported and reserve a margin where exact accounting is unavailable. Reject invalid budgets; define any history reduction or evidence selection explicitly instead of silently truncating arbitrary content.

Large advertised context is not an instruction to fill every request. Start with a bounded evidence budget and measure missed evidence, supported answers, latency, and actual usage before increasing it. A completed response can be too short or incomplete if reasoning consumes its output reservation.

When changing the model, verify its callable ID, route, input/output limits, supported parameters, pricing, and quality on the same examples. Do not carry a larger model's limits into a smaller one. Record the effective model, route/tier, configuration, prompt version, and available usage in evaluation results. Never include credentials.

Never print secrets in logs, evaluation artifacts, or error messages. Environment values containing credentials must not be exposed to a browser bundle.

Configuration makes values adjustable; it does not make every change immediately compatible. Embedding model/dimension and parsing/chunking changes can require a rebuilt index. Document those transitions before supporting a setting.

Keep schemas, prompt templates, fixtures, and dependency versions in versioned files. The environment file holds secrets and deployment/runtime values, not the entire behavior of the application.
