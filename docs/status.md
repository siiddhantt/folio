# Folio status

Updated: 2026-11-06

## Accepted direction

- Product name: Folio.
- Public source development is acceptable. Hosting a public service is a separate decision.
- Use OpenAI initially; credentials and available credit must be verified before live model calls.
- Preserve user ownership through explanations, staged architectural decisions, and bounded agent delegation.
- Implement small vertical slices with behavior tests written first.
- Maintain reviewed, pinned skills and durable repository guidance.
- General-purpose document assistance, using facts in reports/documents as initial examples rather than a domain restriction.
- Commentless, Git-ignored local `.env` with a safe configuration template.

## Completed

- Created product-focused agent instructions, an initial requirements agreement, a staged decision guide, and an AI-use record.
- Accounted for document processing, conversations, persistence, monitoring, documentation, demonstrations, and optional capabilities in the requirements.
- Identified the difference between required PostgreSQL storage and the open retrieval-engine choice.
- Installed and verified the selected skills and their provenance; see `docs/skills.md`.
- Created a commentless configuration template. No usable credential is stored in the repository.
- Published the initial source and documentation at [siiddhantt/folio](https://github.com/siiddhantt/folio).
- Checked primary technical documentation and read practitioner guidance directly; the decision guide records the relevant sources and limits of the evidence.
- Verified documentation links, requirement-ledger coverage, excluded local data/secrets, and installed skill integrity. No application test results are claimed.

## In progress

- OpenAI API funding and credential setup remain unresolved. No live model calls have run.
- Supported-document scope and subsequent design choices remain under discussion.

## Next decision

Choose the supported document boundary (D02). D01's general-purpose direction is accepted. Then discuss conversation scope and processing behavior before selecting parser and search components.

All architectural recommendations in the decision guide remain proposals until explicitly accepted. No application implementation has begun.

## Handoff discipline

Record accepted decisions, evidence, checks actually run, and the next unresolved question here after each meaningful increment. Never replace unknowns with assumed acceptance.
