# Model-call reservations

November 12, 2026. Option 1 accepted before conversation implementation.
The owner accepted hybrid history compression and sharing the existing allowance
across summaries, indexing, question embeddings, rewriting, answers and memory.
The $1 cumulative and $0.40 document amounts are unchanged. New upload policies
use version 2: the configured stage input allowance plus maximum output.

## Why the previous hold was too large

`ai/tokens.py` already counts serialized messages/schema with the selected
tokenizer, adds a margin and checks Folio's configured input allowance. However,
the previous financial reservation ignored that smaller allowance and priced the
provider's maximum prompt capacity. For the selected DeepSeek route, the separate
prompt ceiling is unspecified, so it substitutes the 1,048,576-token context
ceiling. The output maximum is reserved separately.

The saved public-document summary illustrates the difference: Folio estimated
36,145 input tokens including its margin, reserved 1,048,576 input tokens and
$0.3342336, then recorded 27,988 billed input tokens, 412 output tokens and an
actual charge of $0.0088908. This one observation does not prove every future
local estimate overcounts, or calibrate the margin across models and payloads.

A reservation is money temporarily unavailable to other jobs; it is not an
extra provider payment. Oversized holds prevent useful concurrent work even
when actual charges are small.

## Options and recommendation

| Option | Advantage | Tradeoff |
| --- | --- | --- |
| Folio's configured stage input allowance + maximum output | Predictable, conservative within local admission; reuses existing settings | Holds more than a short request needs; input counting is still an estimate. |
| Actual request estimate + margin + maximum output | Smaller holds for short requests | More variable capacity and smaller uncertain-call holds; requires careful calibration. |
| Retain full provider-capacity holds | Preserves the current published-capacity financial bound | Blocks background/answer overlap and can reject inexpensive work; a tighter strict bound needs verified provider support. |

The owner selected the first option for this increment. The priced input ceiling is the
smallest applicable Folio stage allowance, verified provider prompt ceiling and
combined-context space left after maximum output. The complete local count plus
margin must fit that ceiling before transmission. Do not add a new percentage
buffer or reduce the output cap just to make the reservation smaller.

`hold = admitted stage input ceiling × input rate + maximum output × output rate`

For the current flat $0.30/M input and $1.20/M output route:

| Example | Input priced | Maximum output | Hold |
| --- | ---: | ---: | ---: |
| Legacy summary calculation | 1,048,576 | 16,384 | $0.3342336 |
| New summary calculation | 64,000 | 16,384 | $0.0388608 |
| Illustrative answer limits | 16,384 | 4,096 | $0.0098304 |
| Illustrative memory limits | 16,384 | 2,048 | $0.0073728 |

The summary limits already exist; answer/memory numbers are examples, not
selected defaults or measured costs. Background admission must also leave the
agreed foreground allowance. A running call cannot surrender its hold merely
because another question arrives.

## Guarantee and failure behavior

Folio's input allowance is enforced against local token counting, not a
provider-enforced billed-input ceiling. Therefore both smaller-hold options are
operational spending controls, not an absolute no-overshoot guarantee. The
owner accepted this estimate-based policy without changing allowance amounts.
A provider-rendering difference could make actual usage exceed the
hold. Do not hide that by capping the recorded charge or increasing the allowance.

Before dispatch, lock the shared budget account and atomically check known
charges plus unresolved holds plus the new hold against both limits. Do not
assume cache discounts. Keep pinned routes, price filters and bounded output.
When the response arrives, replace its hold with the full reported cost.
Timeouts/missing costs retain the original hold; retries need another admission.

Record and visibly pause new paid admission if actual charges exceed a hold or
reported input exceeds the reserved input ceiling, pending review/reconciliation.
Already-running requests can still incur costs and must settle. A pause cannot
retroactively guarantee the original limit; some overage remains possible under
estimate-based admission. Reconciliation must not silently forgive unresolved
charges. Preserve a provider response ID when one exists; a response lost before
receiving an ID cannot necessarily be looked up through the generation endpoint.

The summary late-billing correction records cost even when the worker has lost
ownership. Billing settles its exact
invocation even after ownership expires, while stale answer publication remains
forbidden. The embedding lifecycle already separates these two responsibilities.

The reservation version is frozen in the upload's summary policy, not an editable
environment setting. A missing version means legacy version 1. New work uses
version 2; legacy retries keep their old calculation so manifest
comparison does not fail merely due to deployment. Never shrink existing unknown
holds, rewrite historical charges or recreate the budget account.

## Follow one call

1. `summaries/config.py` captures the policy at upload. `ai/tokens.py` checks the
   complete input and calculates the hold without reducing output headroom.
2. `summaries/lifecycle.py` reserves through `ai/budget.py`. A database transaction
   locks the single account row until the check and reservation are both saved.
   A second worker waits briefly, then sees the first hold; both cannot spend the
   same remaining dollars. The existing primary key finds that single row; no
   new search index is needed.
3. The provider call runs outside the transaction. A slow model therefore does
   not keep the database lock held. The output token ceiling remains a provider
   limit; dollars do not cause an additional mid-response cutoff.
4. The completion transaction replaces the hold with the actual reported cost.
   For example, a $0.0388608 hold and a $0.009 bill free $0.0298608 for later work.
   A timeout without a bill retains the hold. If a late bill arrives after worker
   recovery, it still settles, but that worker cannot overwrite the current result.

Migration 009 adds only an admission-error field to the existing account. A
reservation overrun sets `RESERVATION_EXCEEDED`; the development console shows
the pause. Existing calls can settle and valid results can publish. The pause
persists across restarts. No automatic reset, new budget, billing service or
resume button is introduced. Review the affected attempts' costs, usage and
saved input manifests before an operator deliberately clears the account flag;
missing bills remain held. Already unavailable runs are not automatically rerun.

Owner exercise: with $0.05 available, two workers each request a $0.0388608 hold.
Explain why only one can start, and why the second may fit after a $0.009 bill.
Then explain why a timed-out first call cannot simply release its hold.

## Small test-first increment

Use the existing token-admission/provider and real-database budget/lifecycle
interfaces. Add one behavior at a time, not a new billing framework:

1. Stage allowance determines the new hold while complete input, schema, margin
   and output checks still reject invalid requests before transmission.
2. A late response records its charge without publishing stale content; an
   overrun pauses further admissions while other in-flight calls still settle.
3. Unknown outcomes preserve their holds; concurrent callers cannot spend the
   same remaining allowance. Extend the same ledger when conversation stages exist.
4. Frozen legacy work keeps its prior calculation and historical spending.

Keep only contract regressions that catch those failures. Deterministic checks
need no live model call. Start chat implementation after this accounting increment
passes; do not combine the reservation fix with conversation schema/UI changes.

## Verified provider boundaries

Current primary OpenRouter docs/spec were checked read-only on November 12:

- No exact Chat Completions input-token preflight endpoint or general hard
  per-request total-dollar cap was documented in the inspected
  [API specification](https://openrouter.ai/openapi.json).
- [`provider.max_price`](https://openrouter.ai/docs/guides/routing/provider-selection)
  filters unit prices; its `request` field filters a flat request fee, not the
  entire token bill. Server-tool `max_cost` stop conditions also are not a hard
  total cap and are outside Folio's current tool-free requests.
- [Key credit limits](https://openrouter.ai/docs/api/reference/limits) constrain
  cumulative key spend. The documented account-level in-flight estimation rollout
  has exclusions and does not establish a universal zero-overshoot guarantee.
  A dedicated key limit could add protection, but no key/account setting was changed.
- [Usage accounting](https://openrouter.ai/docs/use-cases/usage-accounting)
  supplies `usage.cost` and native token counts. Save the generation ID for
  [later reconciliation](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation)
  using the total account charge, not an upstream-only cost field.

Changing provider or adding exact counting can be reconsidered if a strict
smaller bound is essential. It is not required merely to reduce our local hold,
provided the owner accepts the explicit estimate-based policy.
