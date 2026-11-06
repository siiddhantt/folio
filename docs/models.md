# Folio model selection notes

Checked: November 6, 2026. These are observed provider specifications, not Folio quality measurements. Recheck availability, routes, prices, and capabilities before a live evaluation.

OpenRouter is the accepted API gateway. GPT-6 Luna is the preferred first evaluation candidate; no model has yet passed Folio's quality checks. Generation and embeddings are separate choices.

## Candidates

Prices below are USD per million tokens at the listed standard rates. Cached input means an eligible cache read, not every repeated request. Regional routes, service tiers, long prompts, and other charges can change the total.

| OpenRouter model ID listed in the public catalog | Context ceiling | Maximum completion | Input | Cached input | Output |
| --- | ---: | ---: | ---: | ---: | ---: |
| [`openai/gpt-6-luna`](https://openrouter.ai/openai/gpt-6-luna) | 1,050,000 | 128,000 | $0.10 | $0.01 | $0.50 |
| [`openai/gpt-5-nano`](https://openrouter.ai/openai/gpt-5-nano) | 400,000 | 128,000 | $0.05 | $0.005 | $0.40 |
| [`qwen/qwen3.5-flash-02-23`](https://openrouter.ai/qwen/qwen3.5-flash-02-23) | 1,000,000 | 65,536 | $0.065 | Not listed | $0.26 |

All three list structured-output support, but a selected route still needs to support the parameters we send. These specifications do not establish reliable citations or correct answers.

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

## Proposed evaluation

1. Agree a small set of document questions and supporting passages before generating outputs. Include exact facts, missing information, a follow-up, and an ambiguous or conflicting passage.
2. Start with explicit GPT-6 Luna and a standard service tier. Compare supported low-cost reasoning settings before assuming higher effort is needed.
3. Check evidence retrieval separately from generation. A stronger model cannot recover a passage it never received.
4. Compare cheaper candidates only against the same expectations, recording supported claims, citations, useful abstention, failures, latency, and total billed usage.
5. Choose the smallest model/configuration that meets the agreed quality boundary. Retain held-out examples before tuning and record all unsuccessful attempts too.

Decide route/fallback and document-data policies before live calls. Record the actual model/provider/tier; a model ID alone does not identify every execution detail. Required parameters should be enforced rather than silently dropped. Credit availability is separate from an agreed evaluation spending limit. Sources: [OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection), [service tiers](https://openrouter.ai/docs/guides/features/service-tiers).

No inference, embedding request, performance benchmark, or quality evaluation has run. A read-only credential check establishes authentication only.
