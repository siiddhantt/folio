# Folio configuration

Folio's local `.env` is commentless and excluded from Git. `.env.example` is a safe, commentless template; it contains no usable credential.

| Name | Meaning | Current state |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Server-side credential for OpenRouter | Supplied locally; never commit or print its value. |
| `OPENROUTER_BASE_URL` | Base URL for the selected API gateway | `https://openrouter.ai/api/v1` |

No application configuration loader exists yet. Add settings as their behavior is accepted and implemented: model IDs, connection URLs, storage locations, file limits, timeouts, retrieval settings, and usage budgets. Validate them at startup and explain defaults and units here.

## Model and token controls

Configurable model identity and token budgets are accepted requirements. The following names and semantics are a proposed configuration contract; numerical defaults and runtime implementation remain open. They are not added as inert flags to the environment template.

| Proposed setting | Purpose |
| --- | --- |
| `AI_MODEL` | Explicit generation model ID. The current evaluation candidate is `openai/gpt-6-luna`; avoid a moving latest alias in a reproducible comparison. |
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
