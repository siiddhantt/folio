# Folio status

Updated: 2026-11-06

## Accepted direction

- Product name: Folio.
- Public source development is acceptable. Hosting a public service is a separate decision.
- Use OpenRouter as the initial API gateway. GPT-6 Luna is a preferred evaluation candidate; exact model choice and live-call budgets remain open.
- Preserve user ownership through explanations, staged architectural decisions, and bounded agent delegation.
- Implement small vertical slices with behavior tests written first.
- Maintain reviewed, pinned skills and durable repository guidance.
- General-purpose document assistance, using facts in reports/documents as initial examples rather than a domain restriction.
- Commentless, Git-ignored local `.env` with a safe configuration template.
- Text-based PDFs first, with one selected PDF per conversation.
- Configurable generation model and token budgets, with model-specific validation and quality checks when values change.

## Completed

- Created product-focused agent instructions, an initial requirements agreement, a staged decision guide, and an AI-use record.
- Accounted for document processing, conversations, persistence, monitoring, documentation, demonstrations, and optional capabilities in the requirements.
- Identified the difference between required PostgreSQL storage and the open retrieval-engine choice.
- Installed and verified the selected skills and their provenance; see `docs/skills.md`.
- Created a commentless configuration template. No usable credential is stored in the repository.
- Published the initial source and documentation at [siiddhantt/folio](https://github.com/siiddhantt/folio).
- Checked primary technical documentation and read practitioner guidance directly; the decision guide records the relevant sources and limits of the evidence.
- Verified documentation links, requirement-ledger coverage, excluded local data/secrets, and installed skill integrity. No application test results are claimed.
- Verified local credential presence, Git exclusion, and successful OpenRouter authentication using a read-only metadata request. No inference request was made.

## In progress

- Live model quality, request budgets, and runtime configuration remain unverified. Successful credential authentication does not establish model quality or an agreed application spending budget.
- Extraction-coverage policy, runtime boundary, and subsequent design choices remain under discussion.

## Next decision

Resolve detected incomplete extraction (D02), local versus hosted operation (D04), and grounded-answer behavior (D03). The initial format and one-document scope are accepted. Then define processing behavior before selecting parser and search components.

All architectural recommendations in the decision guide remain proposals until explicitly accepted. No application implementation has begun.

## Handoff discipline

Record accepted decisions, evidence, checks actually run, and the next unresolved question here after each meaningful increment. Never replace unknowns with assumed acceptance.
