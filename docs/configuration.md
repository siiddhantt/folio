# Folio configuration

Folio's local `.env` is commentless and excluded from Git. `.env.example` is a safe, commentless template; it contains no usable credential.

The accepted [development console](development-console.md) stores editable
document/summary controls in PostgreSQL. Environment values seed them once;
subsequent console saves survive restarts. Credentials, infrastructure, selected
model/provider, execution supervision and spending allowances remain
environment-managed. The environment values below are initial defaults for
editable controls, not a way to overwrite an existing saved configuration.

| Name | Meaning | Current state |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Server-side credential for OpenRouter | Supplied locally; never commit or print its value. |
| `OPENROUTER_BASE_URL` | Summary gateway URL | `https://openrouter.ai/api/v1`; the embedding client fixes this same gateway URL in code. |

The ingestion loader is [`Settings`](../src/folio/config.py). It validates positive bounds,
retry delays and the timeout relationship at startup. Docker Compose forwards only the
implemented settings. Only the worker receives the OpenRouter credential; it is
never passed to the API, dispatcher or browser bundle. Summaries and indexing
default to disabled.

| Ingestion setting | Default / meaning |
| --- | --- |
| `FOLIO_PORT` | `8000`; Compose exposes the API on localhost only. |
| `FOLIO_WEB_PORT` | `3000`; Compose exposes the web interface on localhost only. |
| `FOLIO_DEVELOPMENT_MODE` | `false`; gates development inspection and configuration routes/UI. Saved controls still apply when hidden. Enable explicitly for local inspection; it is not authentication. Safe lifecycle events are recorded whether or not the view is enabled. |
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

Accepted requests freeze their processing settings. Console saves apply to new
uploads, including their eventual summary policy. Each upload also captures the
environment-managed indexing policy. Changing non-editable `.env`
settings takes effect after recreating services; it does not rewrite old requests.
A worker rejects an old
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
| `FOLIO_SUMMARY_ENABLED` | `false`; initial automatic-summary switch. New uploads capture the saved policy before processing. |
| `FOLIO_SUMMARY_MODEL_ID` | `deepseek/deepseek-v4.1-flash-1017`; fixed comparison model. |
| `FOLIO_SUMMARY_PROVIDER` | `together`; explicitly selected standard route through OpenRouter. The earlier Fireworks route remains supported, without automatic fallback. |
| `FOLIO_SUMMARY_INPUT_LIMIT_TOKENS` | `64000`; complete evidence, instructions, schema and margin must fit. |
| `FOLIO_SUMMARY_MAX_OUTPUT_TOKENS` | `16384`; generous fixed completion ceiling, not a requested visible length or automatic charge. |
| `FOLIO_SUMMARY_TOKEN_MARGIN` | `2048`; positive allowance for uncertain provider framing. |
| `FOLIO_SUMMARY_REASONING_EFFORT` | `none`; checked against model metadata. |
| `FOLIO_SUMMARY_TIMEOUT_SECONDS` | `90`; provider request timeout. |
| `FOLIO_SUMMARY_MAX_ATTEMPTS` | `2`; initial attempt plus at most one automatic retry. |
| `FOLIO_SUMMARY_BUDGET_USD` | `1.00`; existing persistent deployment allowance shared by summaries and embeddings, not reset by restart. |
| `FOLIO_SUMMARY_DOCUMENT_BUDGET_USD` | `0.40`; shared document allowance including summary/embedding retries and uncertain calls. |

Current prompt/schema/preparation versions are 6/4/3. Preparation preserves
parent links alongside text/table content, source IDs and page references. Output
contains an overview and 1–5 cited points, normally 3–5 without padding short
sources. Stored coverage supplies known extraction gaps. Complete available
evidence must fit; there is no truncation, hierarchy, retrieval substitution,
manual generation or generation on reads. Enabling does not backfill old revisions.
See the [summary contract and walkthrough](summaries.md).

For new uploads, runtime settings, summary policy and indexing policy are captured together
before multipart processing. Older requests without a saved summary policy keep
their legacy publication-time capture. Effective
input and code versions are recorded at first admission; retries after admission
must match that manifest. A never-admitted queued run can use newer preparation
code after a deployment, so the manifest is authoritative for actual provenance.

Token admission uses the selected upstream tokenizer plus a margin. New upload
policies reserve the configured input allowance (constrained by provider prompt
and combined-context limits) plus maximum output. With 64,000 input and 16,384
output tokens, the observed DeepSeek rates produce a $0.0388608 hold. The output
ceiling is unchanged. Reservation version 2 is a code-owned policy field; policies
without it retain the legacy $0.3342336 calculation on retries. Existing unknown
holds are never reduced on deployment. This is estimate-based admission, not a
provider-enforced dollar guarantee. Unknown outcomes retain their hold; retries
require a fresh one. Late known charges settle even after ownership expires.
Reported cost or input exceeding its reservation pauses new paid admissions and
appears in the console; running calls can still finish. See [accounting](ai-budget.md).
Invalid summary
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

## Document indexing controls

[`IndexSettings`](../src/folio/indexing/config.py) validates the following settings
forwarded by Compose and listed in `.env.example`. They apply to future uploads
or the first explicit indexing intent for an existing revision. A captured
policy and saved plan are immutable; changing settings does not rewrite stored
chunks, restart unavailable work or backfill old documents. Indexing has no
development-console switch.

| Setting | Default / meaning |
| --- | --- |
| `FOLIO_INDEX_ENABLED` | `false`; enables indexing intent for new uploads. An explicit first intent also uses this value. |
| `FOLIO_INDEX_MODEL_ID` | `openai/text-embedding-3-small`; this is the only accepted value. |
| `FOLIO_INDEX_CHUNK_TOKENS` | `512`; final contextualized chunk ceiling, including headings; valid range 32–8,192. |
| `FOLIO_INDEX_BATCH_SIZE` | `32`; chunks per provider call and worker delivery; valid range 1–32. |
| `FOLIO_INDEX_MAX_CHUNKS` | `4096`; complete-plan bound; valid range 1–10,000. An oversized plan is unavailable, not truncated. |
| `FOLIO_INDEX_TIMEOUT_SECONDS` | `60`; timeout for each provider request; positive and checked against the captured worker execution window. |

The implementation fixes the OpenAI route and its default 1,536 dimensions, with
no fallback or dimension override. It uses Docling peer merging and
`always_emit_headings`, counts final text with `cl100k_base`, and stores the exact
text/hash, ordered source links and versions. Unsupported mapping, lost context
or an oversized chunk prevents publication. Source locations describe whole
elements, not verified character spans. Known extraction gaps and outside-body
exclusions remain visible. Successful batches persist, but the chunks endpoint
requires the complete index to be ready.

Compose does not expose provider, dimensions, embedding price or retry-count
variables. The current indexing defaults allow at most two failed attempts for
the same unfinished batch; a successful batch resets that failure counter.
Retry timing, queue delivery and execution/lease bounds use the shared runtime
policy. These implementation limits are not support for arbitrary model swaps.
See the [indexing walkthrough](indexing.md) for the persisted lifecycle.

The two existing `FOLIO_SUMMARY_*_BUDGET_USD` values above intentionally retain
their names and now govern summaries, embeddings and conversation stages. One locked account
admits calls against combined known charges and uncertain reservations; indexing
does not add or reset an allowance. Embedding admission reserves counted input
plus 16 tokens per chunk at a maximum $0.02 per million input tokens. The client
checks route availability and pricing before invocation. Reported cost replaces
the reservation, including a late response whose vectors no longer have
permission to publish. Missing billing retains the reservation, and each retry
needs a new admission. Summary-specific configuration errors do not invalidate
otherwise valid embedding settings.

Vectors are stored in pgvector 0.8.7 inside the existing PostgreSQL 18 database.
Query embeddings and exact retrieval belong to the separate conversation flow;
they use the pinned index model, not the answer model.

## Answer controls

These settings apply when a new question is accepted. Its policy is saved with
that turn; changing the deployment does not change existing work or answers.
Recreate API/chat-worker after changing the local environment. The development
console does not expose these controls yet.

| Setting | Default and purpose |
| --- | --- |
| `FOLIO_CHAT_MODEL_ID` | `openai/gpt-5.2`, accepted after the limited source-reviewed comparison. |
| `FOLIO_CHAT_PROVIDER` | `openai`, the selected OpenRouter route. |
| `FOLIO_CHAT_INPUT_LIMIT_TOKENS` | `16384`, complete question/instructions/evidence/schema estimate including safety margin. |
| `FOLIO_CHAT_MAX_OUTPUT_TOKENS` | `4096`, completion headroom, not a requested answer length. |
| `FOLIO_CHAT_TOKEN_MARGIN` | `2048`, allowance for uncertain framing/token overhead. |
| `FOLIO_CHAT_REASONING_EFFORT` | `none`, verified for this model/route. |
| `FOLIO_CHAT_TIMEOUT_SECONDS` | `90`, maximum wait per provider request within the saved worker deadline. |
| `FOLIO_CHAT_RETRIEVAL_CHUNKS` | `6`, maximum passages from the conversation's pinned index. |
| `FOLIO_CHAT_HISTORY_LIMIT_TOKENS` | `8000`, selected memory plus unchanged recent exchanges; not an additional model allowance. |
| `FOLIO_CHAT_REWRITE_MODEL_ID` / `PROVIDER` | `openai/gpt-5.2` / `openai`, follow-up resolution through OpenRouter. |
| `FOLIO_CHAT_REWRITE_INPUT_LIMIT_TOKENS` / `MAX_OUTPUT_TOKENS` | `16384` / `1024`; complete resolver request and completion ceiling. |
| `FOLIO_CHAT_REWRITE_REASONING_EFFORT` / `TIMEOUT_SECONDS` | `none` / `90`; frozen per accepted question. |

Prices and model capacity come from validated provider metadata, not these
settings. At the observed GPT-5.2 rates, the answer reservation is $0.086016;
actual reported cost replaces the reservation. Existing deployment/document
allowances are unchanged. Summary settings stay separate. Rewriting reserves
$0.043008 at the same observed rates; successful stages are reused after retry.

### Long-history controls

The accepted memory checkpoint uses the following separate environment settings.
They are captured with newly accepted questions; existing frozen contexts do not
change. The development console does not expose them yet.

| Setting | Default and purpose |
| --- | --- |
| `FOLIO_MEMORY_TRIGGER_TOKENS` | `6000`, start preparing older-history notes after an answer when selected context reaches this size. |
| `FOLIO_MEMORY_TARGET_TOKENS` | `3000`, soft selection target for memory plus recent exchanges. Never permission to cut a message. |
| `FOLIO_MEMORY_KEEP_TURNS` | `2`, minimum recent complete exchanges kept unchanged. |
| `FOLIO_MEMORY_WAIT_SECONDS` | `600`, maximum pending-question wait for required context preparation. |
| `FOLIO_MEMORY_MODEL_ID` / `PROVIDER` | `openai/gpt-5.2` / `openai`, the accepted memory model/route. |
| `FOLIO_MEMORY_INPUT_LIMIT_TOKENS` / `MAX_OUTPUT_TOKENS` | `16384` / `2048`, complete compactor input and generous completion ceiling. |
| `FOLIO_MEMORY_REASONING_EFFORT` / `TIMEOUT_SECONDS` | `none` / `90`. |

Require target < trigger <= hard history allowance. The memory worker uses the
existing execution/lease settings and bounded attempts. A separate queue/worker
lets background work overlap reading and answering; it still shares database,
provider and deployment resources. A required summary can add latency when it
is not ready before the next question.

At the observed rates a memory call reserves $0.057344. Background admission also
checks that enough allowance remains for the next rewrite, answer and bounded
query embedding, but only the memory call receives a reservation. If funds are
tight, background work defers without spending. A question that actually needs
that same job can promote it for ordinary admission; it cannot bypass the
spending boundary or an accounting pause. Actual reported usage replaces the
hold, including late bills from workers that can no longer publish.

When rolling out changes to shared accounting, recreate **all** admitting
processes: API, dispatcher, ingestion/summary/index worker, chat worker and memory
worker. An older worker must not omit a newly introduced charge type. Apply the
migration before starting the new versions; preserve existing data and allowance.

The provider's model/endpoint context limit is a capability to verify, not a capacity that Folio can enlarge by changing an environment variable. The input-fit invariant is:

`assembled input + reserved generated tokens + safety margin <= verified context limit`

Also enforce the selected route's separate ceilings: assembled input must not exceed its maximum prompt tokens, and the output reservation must not exceed its maximum completion tokens. Passing the combined-context check alone is insufficient. If route metadata omits a limit, verify it before relying on that capacity rather than interpreting the missing field as unlimited.

Evidence and any later conversation history share the input allowance; they do not add capacity. The current question, instructions, citation labels, and message-format overhead also need room. Token accounting must match the selected model as closely as supported and reserve a margin where exact accounting is unavailable. Reject invalid budgets; define any history reduction or evidence selection explicitly instead of silently truncating arbitrary content.

Large advertised context is not an instruction to fill every request. Start with a bounded evidence budget and measure missed evidence, supported answers, latency, and actual usage before increasing it. A completed response can be too short or incomplete if reasoning consumes its output reservation.

When changing the model, verify its callable ID, route, input/output limits, supported parameters, pricing, and quality on the same examples. Do not carry a larger model's limits into a smaller one. Record the effective model, route/tier, configuration, prompt version, and available usage in evaluation results. Never include credentials.

Never print secrets in logs, evaluation artifacts, or error messages. Environment values containing credentials must not be exposed to a browser bundle.

Configuration makes values adjustable; it does not make every change immediately compatible. Embedding model/dimension and parsing/chunking changes can require a rebuilt index. Document those transitions before supporting a setting.

Keep schemas, prompt templates, fixtures, and dependency versions in versioned files. The environment file holds secrets and deployment/runtime values, not the entire behavior of the application.
