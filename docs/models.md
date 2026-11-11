# Folio model selection notes

Latest check: November 12, 2026; earlier investigations retain their dates below. These are observed provider specifications, not Folio quality measurements. Recheck availability, routes, prices, and capabilities before a live evaluation.

OpenRouter is the accepted API gateway. DeepSeek V4.1 Flash 1017 is the current
summary evaluation candidate. The owner delegated a cost-conscious
choice; this does not establish model quality. Summary, later chat and embeddings
have separate configuration and evaluation needs.

## Retrieval and answer candidates — November 12

Status: proposed, not accepted or implemented. This research used primary
documentation and public catalogs; no inference, configuration change or paid
evaluation occurred. Chunking, retrieval storage and answer behavior remain open
in decisions D07–D10. OpenRouter remains the accepted gateway.

### Embeddings

| Candidate | Verified input limit / dimensions | Tradeoff |
| --- | --- | --- |
| OpenRouter `openai/text-embedding-3-small` | 8,192 tokens per input; 1,536 dimensions by default | $0.02 per million input tokens; simple hosted boundary, but requires external processing, network recovery and cost accounting. |
| Local `intfloat/e5-small-v2` | 512 tokens; 384 dimensions; English only | No per-call API charge, but model assets, local resource use and tighter splitting limits. CPU latency is unmeasured. |

Recommendation: evaluate OpenAI small at its default dimensions first. Embedding
100,000 tokens would cost about $0.002 at the listed rate, including any repeated
headings or overlap in the actual submitted text. OpenRouter documents a
`dimensions` request field, but the observed OpenAI route metadata does not list
supported parameters; dimension forwarding has not been tested. Default
dimensions avoid depending on that unverified behavior. OpenAI's direct API also
documents separate batch limits; do not infer gateway batch behavior from the
per-input ceiling. Sources: [embedding catalog](https://openrouter.ai/api/v1/embeddings/models),
[gateway request contract](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings),
[OpenAI embedding guide](https://developers.openai.com/api/docs/guides/embeddings).

E5 requires `query: ` and `passage: ` prefixes and normalized vectors. Its model
card warns that longer text truncates, so Folio would need an explicit bound
including prefixes and headings. It is an older checkpoint usable through
maintained SentenceTransformers runtimes, not evidence of ongoing weight updates
or measured Folio quality. Choose it if local processing matters enough to justify
that operational work. Changing embedding models or dimensions requires a
compatible index rebuild. Sources: [E5 model card](https://huggingface.co/intfloat/e5-small-v2),
[runtime options](https://sbert.net/docs/sentence_transformer/usage/efficiency.html).

### Answer generation

Prices are USD per million tokens on the named standard routes, not every route
behind the same model ID. These candidates have not been compared on Folio chat.

| OpenRouter ID / route | Input / output | Context / maximum output |
| --- | --- | --- |
| `openai/gpt-6-luna` / `openai` | $0.10 / $0.50 at short-input rates | 1,050,000 / 128,000; separate prompt cap 922,000 |
| `anthropic/claude-haiku-5.5` / `anthropic` | $0.10 / $0.50 through 100,000 input tokens | 1,000,000 / 128,000; no numeric separate prompt cap listed |
| `deepseek/deepseek-v4.1-flash-1017` / `together` | $0.30 / $1.20 | 1,048,576 / 943,718; no numeric separate prompt cap listed |

Luna's cache-read/write rates are $0.01/$0.125. Above 272,000 input tokens,
full-request rates become $0.20 input, $0.75 output, $0.02 cache read and $0.25
cache write. The gateway encodes a threshold at 272,000; verify exact boundary
behavior before approaching it. Haiku's short-input cache read, five-minute write
and one-hour write rates are $0.01, $0.125 and $0.20; above 100,000 input tokens,
rates become $0.50 input, $2.50 output, $0.05 read, $0.625 five-minute write and
$1.00 one-hour write. Cache-write prices replace ordinary input prices for those
tokens. Do not reserve spending using only headline input/output rates.

Together's DeepSeek cache-read rate remains $0.006. The catalog's lower DeepSeek
headline rate, $0.006 input / $0.50 output, belongs to `relace/fp4`, with $0.005
cache reads. That is a different host and quantization, not a price reduction for
the selected Together route. No route substitution is selected. Sources:
[Luna official specifications](https://developers.openai.com/api/docs/models/gpt-6-luna),
[Luna routes](https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints),
[Haiku specifications](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
[Haiku routes](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints),
[DeepSeek routes](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints).

Recommendation: Luna is the first cost-conscious answer candidate; Haiku is a
reasonable comparison if source support disappoints. This needs deliberate
compatibility work before live evaluation. The installed `tiktoken` 0.14.0 maps
OpenAI small to `cl100k_base` but does not map `gpt-6-luna`; an exact Luna counting
path and Haiku counting integration remain unverified. The current flat-price
guard does not support these tiered/cache-write profiles. Changing only the model
environment value is insufficient. Smaller retrieved inputs could reduce cost,
but cannot substitute for citation and qualification review: the retained
[DeepSeek summary results](summary-evaluation.md) still contain those errors.

Docling's existing HybridChunker is the proposed alternative to a simple
paragraph baseline, not a selected policy. It includes context in token counting,
but embedding text does not retain all provenance. Split fragments may still
refer to whole source items, and large tables can split. Verify pinned-version
behavior and map chunk references to Folio evidence before claiming exact source
locations. See [Docling's contract](https://docling-project.github.io/docling/concepts/chunking/)
and D07. Human-reviewed questions must separately check retrieval of the right
passages and whether answers preserve their facts and qualifications.

## Autoloops / DeepSeek investigation — November 11

Status: deferred by the owner after research on November 11; do not switch to or
test Autoloops. OpenRouter remains selected. No Folio model-quality evaluation occurred.
No credentials, inference calls or runtime configuration were used or changed.

[Autoloops' model page](https://autoloops.ai/models/deepseek-v4.1-flash) advertises
`deepseek-v4.1-flash`, an OpenAI-compatible API at `https://api.autoloops.ai/v1`,
1M context, US hosting and rates of $0.30 input, $1.20 output and $0.006 cached
input per million tokens. It also advertises JSON-schema output and thinking-off
operation. These are published capabilities, not verified response contracts.
Autoloops hosts general text generation despite its voice-agent emphasis.

The public page does not establish the host's separate input/output limits,
strict-schema request syntax/subset, reasoning controls/defaults, billed usage
fields, cache-write or long-context charges, or exact model snapshot. Its
documentation link leads to the upstream model card; the console required login.
The homepage promotes a discount without clarifying its duration on the model
page. Do not assume a discount, cache hit or unlisted charge is accounted for.
The [privacy policy](https://autoloops.ai/privacy) and
[terms](https://autoloops.ai/terms) inspected describe speech transcription;
their audio/transcript promises do not establish text-LLM data handling. Use
public or synthetic evidence for an initial comparison.

DeepSeek's official [October update](https://api-docs.deepseek.com/news/news261017)
and [model listing](https://api-docs.deepseek.com/quick_start/pricing) identify
V4.1-Flash-1017 behind its own `deepseek-flash` alias. Autoloops' alias does not
prove the same snapshot. The upstream [JSON guide](https://api-docs.deepseek.com/guides/json_mode)
documents JSON-object mode; strict tool arguments are separate. Neither proves
Autoloops' strict response-schema behavior. Upstream [thinking controls](https://api-docs.deepseek.com/guides/thinking_mode)
and [output limits](https://api-docs.deepseek.com/api/create-chat-completion/)
must not be copied to a different host without verification.

The official [encoding implementation](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/blob/main/encoding/README.md)
and [tokenizer integration](https://github.com/deepseek-ai/deepseek-recipe/blob/main/docs/tokenizer.md)
provide a model-specific counting path, subject to matching the host's rendering.
Folio cannot silently use its GPT tokenizer for DeepSeek. The prior NIST failure
was output exhaustion; a larger advertised input context does not fix it.

At advertised uncached rates, an illustrative 50,000 input + 2,000 billed output
tokens costs $0.0174; 200,000 + 4,000 costs $0.0648. These are arithmetic examples,
not observed Folio token counts or bills, and exclude retries and unverified fees.
Reasoning, if billed as output, must be included in those output counts.

Earlier recommendation, not selected: a bounded direct-Autoloops comparison on public evidence after
checking the host contract. Keep the generic prompt and source-support review.
The existing `profile()`/`generate()` boundary can accommodate one concrete
adapter; provider-specific counting, request controls and billing need deliberate
implementation. A URL/model environment change alone is insufficient. Missing
monetary usage must remain unknown unless documented billed counters and frozen
rates support explicitly labeled derived costs. The durable queue, evidence,
citation validation, ownership and cumulative budget should remain shared.
No switch, new abstraction framework, budget reset or production claim is implied.

## DeepSeek through OpenRouter — output-budget research

Status: accepted for a bounded comparison after the owner reaffirmed OpenRouter
and deferred Autoloops on November 11. Implementation uses the existing summary
boundary; live outcomes are recorded separately in the evaluation report.

The [OpenRouter catalog](https://openrouter.ai/api/v1/models) identifies
`deepseek/deepseek-v4.1-flash-1017`, tokenizer family `DeepSeek`, optional reasoning
with efforts `none`, `low`, `high`, `max`, enabled by default. The inspected
[route metadata](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints)
includes Fireworks (`fireworks`) and Together (`together`), each advertising
1,048,576 context, 943,718 maximum completion tokens, structured output,
response formatting, reasoning and `max_tokens`. Their listed rates are
$0.30 input / $1.20 output / $0.006 cached input per million, with no listed
fixed fee, cache-write charge or pricing overrides. These are observed metadata,
not Folio runtime measurements. Every inspected route omitted a numeric separate
prompt ceiling; null must not be interpreted as unlimited.

Fireworks was the first selected route because its
[structured-response documentation](https://docs.fireworks.ai/structured-responses/structured-response-formatting)
explicitly supports string and array size constraints during generation, while
warning that output truncation can still leave incomplete JSON. Its
[chat reference](https://docs.fireworks.ai/api-reference/post-chatcompletions)
documents DeepSeek V4.1 thinking-off controls. These provider-wide documents and
the [model listing](https://fireworks.ai/models/deepseek-ai/deepseek-v4p1-flash-1017)
still need an exact-route compatibility check with Folio's schema.

Implemented OpenRouter controls: select one supported standard host, disable fallbacks, require
supported parameters, set `reasoning.effort` to `none`, and start evaluation
with a fixed `max_tokens=16384`. `only:["fireworks"]` also matches provider variants;
it does not uniquely pin the standard endpoint. Narrow the currently observed
variants with `ignore:["fireworks/spot","fireworks/us"]` and rate ceilings
of $0.30 input / $1.20 output per million, then recheck endpoint metadata.
These controls do not freeze future routes or independently enforce cumulative
spending. See [routing semantics](https://openrouter.ai/docs/guides/routing/provider-selection).
They do not change Folio's visible
summary length. OpenRouter's [reasoning guide](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
distinguishes hiding reasoning from disabling it; `exclude` alone does not save
the tokens or bill. A native Fireworks integer thinking cap is not proof that
OpenRouter forwards `reasoning.max_tokens` as a hard DeepSeek cap.

At those listed token rates, the full combined context as a conservative input billing
upper bound plus 16,384 output tokens is $0.3342336. That fits $0.40, but does not
establish a separate input allowance or prove every request size is accepted.
Retain the local 64,000-token bound, model-specific counting and combined-context
check. This explicit DeepSeek exception leaves the prompt cap unknown in its
profile, rather than inventing a verified separate input limit.
The client uses the official tokenizer JSON from immutable upstream revision
`08c8657f02291e11b6f6b63e0e16014f8e748518`, SHA-256
`c90dfa01249db1be4245780a052ede752e1361c612ac6d08e2bdada7d599476b`.
Docker bundles the verified asset and MIT license; runtime loading is offline.
The Rust tokenizer is pinned to 0.23.3; no weights or remote template code run.
Missing billing remains unknown; the cumulative $1 allowance is not reset.

The selected ceiling provides completion headroom, not an accuracy or no-error
guarantee. Validate complete output and citations, then review source support on
the regression document plus a fresh document. No hierarchy, input truncation,
automatic model fallback or adaptive retry is selected. A length termination
publishes no partial summary and retains its specific failure reason and bill.

During integration Fireworks' standard route changed from status 0 to -2.
The first mixed-PDF upload therefore published evidence but stopped summary
admission as unavailable, with no paid invocation. A manual compatibility trial
selects Together's healthy standard route through the same OpenRouter gateway,
at the same observed prices and financial reservation. This is an explicit host
selection, not automatic fallback; frozen Fireworks policies remain Fireworks.

Together's [model catalog](https://docs.together.ai/docs/serverless/models) lists
the exact model and structured outputs. Its context is described as 1,000,000
versus OpenRouter's 1,048,576; Folio's 64,000 input plus 16,384 output is below
both. [Together's schema guide](https://docs.together.ai/docs/inference/chat/structured-outputs)
does not enumerate string/array size-keyword enforcement. Its
[reasoning guide](https://docs.together.ai/docs/inference/chat/reasoning) describes
hybrid-off controls without explicitly listing V4.1, while OpenRouter documents
`reasoning.effort=none`. Metadata support is not proof of host-specific behavior.
Start with a small complete response, inspect local validation and reported
reasoning usage, and retain local validation for every result. One accepted
response cannot prove universal schema-keyword enforcement or factual quality.

## Earlier GPT-5.1 summary comparison

GPT-5.1 with `low` reasoning, prompt 5/schema 3/preparation 3 was an earlier
budgeted comparison. Its frozen final 59-page report run exhausted the 4,096-token
output allowance and published no summary. The unseen historical summary was broadly
grounded but introduced three precision errors: plural relocations, troops placed
at the cabin instead of the surrounding field, and log reuse generalized across
renovations. No general quality or large-input capacity pass is claimed.
The verified standard route has 400,000 context, 272,000 prompt and 128,000
output tokens, at $1.25 input / $10 output per million. Reserving the full
prompt ceiling and 4,096 output tokens costs $0.38096, within the owner's
accepted $0.40 document cap; the $1 total allowance is unchanged. An uncertain
call leaves too little room for another full reservation on that document.

The route advertises no fixed-request charge, cache-write rate or pricing
overrides. GPT-5.1 predates the GPT-5.6 automatic cache-write premium. Both
`gpt-5.1` and `gpt-5.1-2025-11-13` were deprecated October 1, 2026 and retire
April 1, 2027; the recommended replacement is GPT-6 Sol. This is a temporary
compatible evaluation choice, not a long-term deployment selection.
Sources checked November 11: [GPT-5.1 route](https://openrouter.ai/api/v1/models/openai/gpt-5.1/endpoints),
[caching](https://openrouter.ai/docs/features/prompt-caching),
and [lifecycle](https://platform.openai.com/docs/deprecations).

The earlier GPT-5.6 Luna estimate of $0.3761728 omitted automatic cache writes.
Official caching guidance and route rates establish an all-write bound of
`922000 × 0.0000005 + 4096 × 0.0000018 = $0.4683728`. Cache-write rates replace
ordinary input rates rather than adding to them. This exceeds the approved
$0.40 cap; no Luna call was made and the existing flat-price guard remains.

## Earlier Mini comparison

GPT-5 Mini replaced the initial Nano candidate after a live Nano result failed
citation-support review. Mini with prompt 3 and minimal reasoning selected better
sources but was verbose and weakened optional wording. Prompt 4 with `low`
reasoning still failed some citation/qualification checks on the report; the
mixed fixture passed narrow source review. No general quality pass is claimed. See the
[recorded calls and source review](summary-evaluation.md).

The verified Mini standard route advertises 400,000 context, 272,000 prompt and
128,000 output tokens, with flat prices of $0.25 input / $2 output per million.
The configured 4,096 output tokens yield a full-route reservation of $0.076192:
`272000 × 0.25 / 1000000 + 4096 × 2 / 1000000`. This fit the original $0.10 document
allowance, but an uncertain first call retaining the reservation leaves too
little for another full reservation. Two configured attempts do not guarantee
two affordable calls. The 64,000 input limit and 2,048-token margin remain.
[Mini route metadata](https://openrouter.ai/api/v1/models/openai/gpt-5-mini/endpoints)
was checked November 11, 2026.

Mini is also temporary: both `gpt-5-mini` and `gpt-5-mini-2025-08-07` retire
December 11, 2026; OpenAI names `gpt-5.6-terra` as the replacement. Configuring
that replacement does not establish compatibility with this slice's pricing,
tokenizer or reservation limits.

## Initial Nano comparison and route research

Nano was the initial temporary evaluation choice. OpenAI deprecated both `gpt-5-nano` and
`gpt-5-nano-2025-08-07` on June 11, 2026, with shutdown scheduled for December 11,
2026; its recommended replacement is `gpt-5.6-luna`. OpenRouter currently lists
Nano, but that listing does not promise availability after the upstream shutdown.
See [OpenAI's deprecation notice](https://developers.openai.com/api/docs/deprecations).

Nano advertises strict structured output and has a known upstream `o200k_base`
tokenizer mapping. Its selected route advertises 400,000 combined context tokens,
272,000 maximum prompt tokens and 128,000 maximum completion tokens. Folio starts
with a much smaller 64,000-token input admission limit, a 2,048-token counting
margin and 4,096 generated tokens including reasoning. `minimal` reasoning
was selected for Nano; it cannot disable reasoning entirely.

At standard prices of $0.05 input / $0.40 output per million, 48,000 input and
2,000 total output tokens illustrate a $0.00320 call. Actual usage and costs must
be recorded; fees, retries and other charges are separate. For admission, reserve
the entire route prompt ceiling plus configured maximum output: $0.0152384 at
the observed rates. This protects the spending allowance from uncertainty in
local message-wrapper counting. An uncertain call retains that full allowance.

Luna remains a useful later comparison, but current upstream `tiktoken` has no
GPT-6/Luna mapping. OpenAI's exact token-count endpoint requires a direct key;
an equivalent OpenRouter endpoint was not found in its documented API. Do not
pretend a different model's tokenizer is exact for Luna. Other configured models
must have a supported tokenizer and a complete, compatible provider profile;
unknown capabilities stop before generation.

The earlier client accepted only a verified OpenAI standard route with numeric
input/output/context limits, supported parameters and compatible flat pricing.
It rejects price overrides and unsupported charges. The November 11 route check
found no nondeprecated replacement satisfying those constraints and the then-$0.10
full-route reservation limit: GPT-5.4 Nano is deprecated and lacks a numeric
prompt cap; GPT-5.4 Mini lacks that cap; GPT-5.2 exceeds the allowance. GPT-5.6
Luna has tiered pricing; the initial $0.3761728 calculation excluded cache writes
and is corrected above. GPT-6 Luna's initial $0.187472 calculation likewise
excluded cache writes; it also has tiered pricing and
the unresolved tokenizer mapping. GPT-5 Mini fits but shares Nano's retirement.
These are compatibility findings, not comparative summary-quality results.

Sources checked November 11: [5.4 Nano routes](https://openrouter.ai/api/v1/models/openai/gpt-5.4-nano/endpoints),
[5.4 Mini routes](https://openrouter.ai/api/v1/models/openai/gpt-5.4-mini/endpoints),
[5.2 routes](https://openrouter.ai/api/v1/models/openai/gpt-5.2/endpoints),
[5.6 Luna routes](https://openrouter.ai/api/v1/models/openai/gpt-5.6-luna/endpoints),
and [6 Luna routes](https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints).

Cheaper advertised alternatives have unresolved tradeoffs. Qwen3.5-Flash's
gateway strict-schema claim differs from Alibaba's documented JSON-object-only
support for that model. A DeepSeek V4.1 Flash route advertises lower input prices,
but its separate prompt ceiling is absent and its provider's direct price differs.
Neither is adopted solely from a cheap catalog listing.

Direct OpenAI standard rates match the selected gateway rates. OpenRouter also
offers discounted Flex/Batch routes; these are distinct tiers with different
execution tradeoffs. No direct account, additional key or tier switch is needed
for this first standard-route comparison.

Sources: [Nano model](https://developers.openai.com/api/docs/models/gpt-5-nano),
[Nano routes](https://openrouter.ai/api/v1/models/openai/gpt-5-nano/endpoints),
[tokenizer mappings](https://github.com/openai/tiktoken/blob/main/tiktoken/model.py),
[token counting](https://developers.openai.com/api/docs/guides/token-counting),
[Alibaba structured output](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output),
[DeepSeek route metadata](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints),
[Relace pricing](https://relace.ai/pricing),
[OpenRouter tiers](https://openrouter.ai/docs/guides/features/service-tiers).

## Candidates

Prices below are USD per million tokens at the listed standard rates. Cached input means an eligible cache read, not every repeated request. Regional routes, service tiers, long prompts, and other charges can change the total.

| OpenRouter model ID listed in the public catalog | Context ceiling | Maximum completion | Input | Cached input | Output |
| --- | ---: | ---: | ---: | ---: | ---: |
| [`openai/gpt-6-luna`](https://openrouter.ai/openai/gpt-6-luna) | 1,050,000 | 128,000 | $0.10 | $0.01 | $0.50 |
| [`openai/gpt-5-nano`](https://openrouter.ai/openai/gpt-5-nano) | 400,000 | 128,000 | $0.05 | $0.005 | $0.40 |
| [`openai/gpt-5-mini`](https://openrouter.ai/openai/gpt-5-mini) | 400,000 | 128,000 | $0.25 | $0.025 | $2.00 |
| [`qwen/qwen3.5-flash-02-23`](https://openrouter.ai/qwen/qwen3.5-flash-02-23) | 1,000,000 | 65,536 | $0.065 | Not listed | $0.26 |

These models list structured-output support, but a selected route still needs to support the parameters we send. These specifications do not establish reliable citations or correct answers.

Routes can impose a separate input ceiling. Luna's observed OpenAI route lists 922,000 maximum prompt tokens, alongside its 1,050,000 combined context and 128,000 completion limit. All three limits must be respected; a smaller output request does not automatically increase the allowed prompt size.

The older `openai/gpt-5.6-luna` lists $0.20 input and $1.20 output at standard rates, so it is not the lower-cost Luna candidate. Avoid the moving `~openai/gpt-luna-latest` alias for repeatable comparisons. Canonical snapshot metadata is not assumed to be a callable model ID unless verified.

The GPT-5 Nano catalog and OpenAI route advertise 128,000 completion tokens, while an Azure endpoint reports a conflicting larger value. Use the conservative advertised figure until that endpoint discrepancy is resolved. The Qwen candidate's observed provider is Alibaba Cloud International. Neither alternative has been evaluated on Folio documents.

Sources: [OpenRouter public catalog](https://openrouter.ai/api/v1/models), [Luna endpoints](https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints), [Nano endpoints](https://openrouter.ai/api/v1/models/openai/gpt-5-nano/endpoints), and [OpenAI Luna specifications](https://developers.openai.com/api/docs/models/gpt-6-luna).

## Context, reasoning, and cost

The context ceiling is the maximum room for a request and its generated tokens, not the amount Folio should send. The [configuration guide](configuration.md) separates input, evidence, history, and generated-token budgets.

Luna supports reasoning efforts `none`, `low`, `medium`, `high`, `xhigh`, and `max`, with `medium` the documented default. Do not assume that another model's effort names work with Luna. The cheaper Nano candidate requires reasoning; its smaller nominal token price does not guarantee a cheaper completed answer.

Reasoning tokens are billed as output and consume the completion allowance. Hiding them from the response does not remove their cost. A small output cap can therefore leave too little room for the visible answer. Compare effective cost and usable answers, not just the output text length. Sources: [OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens) and [OpenAI Luna specifications](https://developers.openai.com/api/docs/models/gpt-6-luna).

Luna's OpenAI documentation applies higher full-request prices above 272,000 input tokens: $0.20 input, $0.02 cached input, and $0.75 output per million tokens. OpenRouter's endpoint metadata encodes a pricing threshold at 272,000; exact boundary behavior should be checked if a request ever approaches it. A modest Folio evidence budget should stay far below that boundary. Explicit cache-write pricing can also apply; do not assume all caching is free. [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [OpenRouter endpoint metadata](https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints).

Illustration only: 8,000 uncached input tokens and 1,500 total billed output tokens at Luna's short-context standard rates cost $0.00155 for one successful generation. This excludes embeddings, document summaries, extra reasoning beyond that assumed total, retries, gateway credit-purchase fees, taxes, and other services. It is not a measured Folio request cost.

## Summary evaluation checkpoint

1. Agree human-reviewed summary expectations and supporting passages across different document types. Include important qualifications, numbers, contradictions, extraction gaps and embedded instructions.
2. Evaluate the accepted DeepSeek candidate on the explicitly selected Together standard route with frozen prompt 6/schema 4/preparation 3, `none` reasoning and 16,384 output capacity, within the persistent $1 deployment and $0.40 document allowances. Retain GPT-5.1, Nano and Mini results as development comparisons.
3. Check extraction coverage separately from generation. This slice sends complete available evidence; retrieval is not implemented.
4. Compare cheaper candidates only against the same expectations, recording supported claims, citations, useful abstention, failures, latency, and total billed usage.
5. Choose the smallest model/configuration that meets the agreed quality boundary. Retain held-out examples before tuning and record all unsuccessful attempts too.

Decide route/fallback and document-data policies before live calls. Record the actual model/provider/tier; a model ID alone does not identify every execution detail. Required parameters should be enforced rather than silently dropped. Credit availability is separate from an agreed evaluation spending limit. Sources: [OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection), [service tiers](https://openrouter.ai/docs/guides/features/service-tiers).

The first ten live development calls cost $0.20725480, matching PostgreSQL and OpenRouter
usage metadata, with no uncertain billing. The final NIST call exhausted its
output allowance; its second attempt stopped before another paid call because
the document allowance could not cover a new reservation. The unseen historical
document produced a saved result but failed a clean source-support review for the
precision errors above. Calls are recorded in the [evaluation report](summary-evaluation.md).
These observations have exposed failures,
not established a quality pass or general benchmark. No embeddings are implemented.
Deterministic tests establish software contracts only. The [summary contract](summaries.md)
records the generic prompt: document-specific reference facts are not production instructions.
The accepted DeepSeek checkpoint uses these failures as regression examples and
adds an independently read fresh technical document. The existing spending
authorization remains $0.40 per document and $1 total; it is not reset for this comparison.
